from comicprice.pricing import estimate


def test_insufficient_data():
    e = estimate([1000, 1100])
    assert e.status == "insufficient_data" and e.median_minor is None


def test_median_ok():
    e = estimate([1000, 1100, 1200])
    assert e.status == "ok" and e.median_minor == 1100


def test_outlier_rejected():
    e = estimate([1000, 1050, 1100, 1150, 1200, 99_999_99])
    assert e.n == 6 and e.n_used == 5 and e.median_minor == 1100
