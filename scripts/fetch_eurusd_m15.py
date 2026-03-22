"""Fetch and display normalized EURUSD M15 bars from MT5."""

from src.data.market_data import fetch_market_data
from src.data.mt5_client import MT5Client


def main() -> int:
    """Initialize MT5, fetch EURUSD M15 bars, print summary, and exit."""

    client = MT5Client()
    try:
        client.initialize()
        dataframe = fetch_market_data(
            client=client, symbol="EURUSD", timeframe="M15", count=200
        )

        print(f"rows: {len(dataframe)}")
        print(f"columns: {list(dataframe.columns)}")
        print("head:")
        print(dataframe.head())
        print("tail:")
        print(dataframe.tail())
        return 0
    finally:
        if client.is_connected():
            client.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
