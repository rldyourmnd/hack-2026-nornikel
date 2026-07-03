

def test_parse_time_scope_last_n_years() -> None:
    from nornikel_kg.domain.dates import parse_time_scope

    assert parse_time_scope("публикации за последние 5 лет", now_year=2026) == (2021, None)
    assert parse_time_scope("experiments for the last 3 years", now_year=2026) == (2023, None)
    assert parse_time_scope("данные с 2019 года", now_year=2026) == (2019, None)
    assert parse_time_scope("работы до 2015 года", now_year=2026) == (None, 2015)
    assert parse_time_scope("в 2018–2022 годах", now_year=2026) == (2018, 2022)
    # bare year mention is a fact, not a scope
    assert parse_time_scope("температура 1963 K и проба 2020", now_year=2026) == (None, None)


def test_parse_time_scope_requires_year_marker() -> None:
    from nornikel_kg.domain.dates import parse_time_scope

    assert parse_time_scope("нагрев до 2000 градусов", now_year=2026) == (None, None)
    assert parse_time_scope("раствор с 2019 мг/л натрия", now_year=2026) == (None, None)
