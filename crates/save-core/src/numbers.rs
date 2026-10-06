pub fn normalize(value: &str) -> Result<(f64, i64), String> {
    let text = value.trim().to_lowercase();
    let (mant, exp) = if let Some((m, e)) = text.split_once('e') {
        (
            m.parse::<f64>().map_err(|_| "Invalid number")?,
            e.parse::<i64>()
                .map_err(|_| "Exponent must be a 64-bit integer")?,
        )
    } else {
        (text.parse::<f64>().map_err(|_| "Invalid number")?, 0)
    };
    if !mant.is_finite() {
        return Err("Number must be finite".into());
    }
    if mant == 0.0 {
        return Ok((0.0, 0));
    }
    let mut owned = mant.abs();
    let mut exp = exp;
    while owned >= 10.0 {
        owned /= 10.0;
        exp = exp.checked_add(1).ok_or("Exponent overflow")?;
    }
    while owned < 1.0 {
        owned *= 10.0;
        exp = exp.checked_sub(1).ok_or("Exponent overflow")?;
    }
    Ok((owned.copysign(mant), exp))
}

// Python's .12g: retain 12 significant digits and remove insignificant zeroes.
fn significant(value: f64) -> String {
    if !value.is_finite() {
        return if value.is_nan() {
            "nan".into()
        } else if value < 0.0 {
            "-inf".into()
        } else {
            "inf".into()
        };
    }
    if value == 0.0 {
        return "0".into();
    }
    let scientific = format!("{value:.11e}");
    let (mantissa, exponent) = scientific.split_once('e').unwrap();
    let exponent: i32 = exponent.parse().unwrap();
    if !(-4..12).contains(&exponent) {
        format!(
            "{}e{:+03}",
            mantissa.trim_end_matches('0').trim_end_matches('.'),
            exponent
        )
    } else {
        let precision = (11 - exponent).max(0) as usize;
        let fixed = format!("{value:.precision$}");
        if fixed.contains('.') {
            fixed.trim_end_matches('0').trim_end_matches('.').into()
        } else {
            fixed
        }
    }
}

pub fn display(owned: f64, exp: i64) -> String {
    if owned == 0.0 {
        return "0".into();
    }
    if !owned.is_finite() {
        return significant(owned);
    }
    let fallback = || format!("{}e{}", significant(owned), exp);
    if !(-300..=300).contains(&exp) {
        return fallback();
    }
    let value = owned * 10f64.powi(exp as i32);
    if !value.is_finite() || value == 0.0 {
        return fallback();
    }
    if (1e-6..1e16).contains(&value.abs()) {
        if (value - value.round()).abs() < 1e-9 {
            return format!("{:.0}", value.round());
        }
        return significant(value);
    }
    fallback()
}
