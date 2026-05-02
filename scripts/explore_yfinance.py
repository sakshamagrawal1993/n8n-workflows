import yfinance as yf
import json
import sys

def explore(ticker):
    print(f"Exploring data for {ticker}...")
    t = yf.Ticker(ticker)
    
    data = {
        "info": t.info,
        "fast_info": {
            "currency": t.fast_info.currency,
            "exchange": t.fast_info.exchange,
            "market_cap": t.fast_info.market_cap,
            "day_high": t.fast_info.day_high,
            "day_low": t.fast_info.day_low,
        },
        "analyst_price_target": t.analyst_price_target if hasattr(t, 'analyst_price_target') else None,
        "growth_estimates": t.growth_estimates.to_json() if hasattr(t, 'growth_estimates') and not t.growth_estimates.empty else None,
        "recommendations": t.recommendations.to_json() if hasattr(t, 'recommendations') and not t.recommendations.empty else None,
        "calendar": t.calendar if hasattr(t, 'calendar') else None,
    }
    
    # Clean up the data to be JSON serializable
    # Some fields in t.info might be complex objects
    return data

if __name__ == "__main__":
    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    try:
        res = explore(ticker)
        # Just print a summary for now
        print("\n--- INFO ---")
        print(f"Name: {res['info'].get('longName')}")
        print(f"Sector: {res['info'].get('sector')}")
        print(f"Market Cap: {res['fast_info'].get('market_cap')}")
        print(f"Current Price: {res['info'].get('currentPrice')}")
        
        # Save to a json file for deep inspection
        with open(f"{ticker}_yfinance_data.json", "w") as f:
            json.dump(res, f, default=str, indent=2)
        print(f"\nFull data saved to {ticker}_yfinance_data.json")
        
    except Exception as e:
        print(f"Error: {e}")
