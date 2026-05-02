import yfinance as yf
import json
import sys

def get_deep_data(ticker):
    t = yf.Ticker(ticker)
    
    # Get basic info
    info = t.info
    
    # Extract only the most useful fields for an LLM agent
    useful_info = {
        "symbol": ticker,
        "name": info.get("longName"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "description": info.get("longBusinessSummary"),
        "currentPrice": info.get("currentPrice"),
        "targetMeanPrice": info.get("targetMeanPrice"),
        "recommendationKey": info.get("recommendationKey"),
        "numberAnalystRatings": info.get("numberOfAnalystOpinions"),
        "trailingPE": info.get("trailingPE"),
        "forwardPE": info.get("forwardPE"),
        "marketCap": info.get("marketCap"),
        "fiftyTwoWeekHigh": info.get("fiftyTwoWeekHigh"),
        "fiftyTwoWeekLow": info.get("fiftyTwoWeekLow"),
        "dividendYield": info.get("dividendYield"),
        "totalCash": info.get("totalCash"),
        "totalDebt": info.get("totalDebt"),
        "operatingCashflow": info.get("operatingCashflow"),
        "freeCashflow": info.get("freeCashflow"),
    }
    
    return useful_info

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No ticker provided"}))
        sys.exit(1)
        
    ticker = sys.argv[1]
    try:
        data = get_deep_data(ticker)
        print(json.dumps(data, indent=2))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
