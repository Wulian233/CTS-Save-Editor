import struct

from .models import CustomVarEntry, MetaVarEntry, StringRecord


def decode_7bit_int(buf: bytes, pos: int) -> tuple[int, int]:
    value = 0

    for count in range(5):
        i = pos + count
        if i >= len(buf):
            raise ValueError("Unexpected EOF while reading 7-bit int")

        b = buf[i]
        value |= (b & 0x7F) << (7 * count)

        if (b & 0x80) == 0:
            return value, count + 1

    raise ValueError("7-bit int too large")


def encode_7bit_int(value: int) -> bytes:
    if value < 0:
        raise ValueError("length must be >= 0")

    out = bytearray()
    v = value

    while v >= 0x80:
        out.append((v & 0x7F) | 0x80)
        v >>= 7

    out.append(v)
    return bytes(out)


def scan_string_records(data: bytes) -> list[StringRecord]:
    records: list[StringRecord] = []
    n = len(data)
    i = 0

    while i + 6 <= n:
        i = data.find(b"\x06", i)
        if i < 0:
            break

        if i + 6 > n:
            break

        obj_id = int.from_bytes(data[i + 1 : i + 5], "little", signed=False)
        len_pos = i + 5

        try:
            strlen, len_size = decode_7bit_int(data, len_pos)
        except ValueError:
            i += 1
            continue

        value_start = len_pos + len_size
        value_end = value_start + strlen

        if value_end > n:
            i += 1
            continue

        try:
            text = data[value_start:value_end].decode("utf-8")
        except UnicodeDecodeError:
            i += 1
            continue

        records.append(
            StringRecord(
                pos=i,
                end=value_end,
                object_id=obj_id,
                text=text,
                len_pos=len_pos,
                len_size=len_size,
                value_start=value_start,
                value_end=value_end,
            )
        )

        i = value_end

    return records


def extract_custom_vars(records: list[StringRecord]) -> list[CustomVarEntry]:
    record_by_pos = {record.pos: record for record in records}
    entries: list[CustomVarEntry] = []

    for key_record in records:
        if not key_record.text:
            continue

        value_record = record_by_pos.get(key_record.end)
        if value_record is None:
            continue

        if key_record.object_id + 1 != value_record.object_id:
            continue

        entries.append(
            CustomVarEntry(
                key=key_record.text,
                value=value_record.text,
                value_len_pos=value_record.len_pos,
                value_len_size=value_record.len_size,
                value_start=value_record.value_start,
                value_end=value_record.value_end,
            )
        )

    return entries


def build_item_save_record_index(data: bytes) -> dict[int, int]:
    result: dict[int, int] = {}
    n = len(data)
    i = 0

    while True:
        idx = data.find(b"\x01", i)
        if idx < 0:
            break

        # record:
        # 0x01 + object_id(4) + 0x25 + ... + owned(double) + exponent(int64)
        #
        # 后续 extract_meta_vars 会读取:
        # owned    at idx + 9,  size 8
        # exponent at idx + 17, size 8
        # 所以至少需要 idx + 25 <= n
        if idx + 25 <= n and data[idx + 5] == 0x25:
            object_id = int.from_bytes(
                data[idx + 1 : idx + 5],
                "little",
                signed=False,
            )
            result.setdefault(object_id, idx)

        i = idx + 1

    return result


def find_item_save_record(data: bytes, object_id: int) -> int | None:
    pat = b"\x01" + object_id.to_bytes(4, "little", signed=False)
    idx = data.find(pat)

    while idx >= 0:
        if idx + 25 <= len(data) and data[idx + 5] == 0x25:
            return idx

        idx = data.find(pat, idx + 1)

    return None


def extract_meta_vars(data: bytes, records: list[StringRecord]) -> list[MetaVarEntry]:
    entries: list[MetaVarEntry] = []
    item_index = build_item_save_record_index(data)
    n = len(data)

    for key_record in records:
        if not key_record.text:
            continue

        p = key_record.end

        # 0x09 + object_id(4)
        if p + 5 > n or data[p] != 0x09:
            continue

        ref_obj_id = int.from_bytes(
            data[p + 1 : p + 5],
            "little",
            signed=False,
        )

        obj_pos = item_index.get(ref_obj_id)
        if obj_pos is None:
            continue

        if obj_pos + 25 > n:
            continue

        owned = struct.unpack_from("<d", data, obj_pos + 9)[0]
        exponent = struct.unpack_from("<q", data, obj_pos + 17)[0]

        entries.append(
            MetaVarEntry(
                key=key_record.text,
                object_id=ref_obj_id,
                owned=owned,
                exponent=exponent,
                object_record_pos=obj_pos,
            )
        )

    return entries
