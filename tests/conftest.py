# Pytest configuration for gr-k-gdss tests.
# Register custom marks so "pytest -m 'not slow'" works without warnings.
def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "slow: marks test as slow (e.g. TestT1SetKeyMessagePort, ~1 min). Skip with: pytest -m 'not slow'",
    )
