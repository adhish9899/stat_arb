
'''
pandas == 1.1.4
numpy == 1.18.0
yfinance == 0.1.55
'''

import pandas as pd
import numpy as np
import datetime as dt
import yfinance as yf


## Please change DATA PATH accordingly after extracting the data zip file. 
DATA_PATH = lambda x: "data/%s.csv" %(x)

pair_list = [["GOOGL", "GOOG"], ["FOXA", "FOX"], ["NWSA", "NWS"]]

## Trading Logic Config
config = {
    "min_entry_exit_spread_diff" : 30, # bps
    "look_back_days" : 5,
    "threshold" : [0.9, 0.95],
    "sq_thresh_diff" : 0.4, 
    "sq_time" : dt.time(15, 50),
    }

## Assumed Slippage
slippage_per_leg = 2.5e-4 # bps

def get_stock_data(stock_name):
    
    '''
    Parameters:
    
        1. stock_name : str        
            Name of the stock you want to fetch data of.
    

    Returns:
        1. df: pd.DataFrame
            Intra day data of the stock
        
        2. eod_df: pd.DataFrame
            End of day data of the stock from Yahoo Finace.
    
    NOTE:
        1. For intra day data, IEX is the data souce. (https://iexcloud.io/)
    
    '''

    df = pd.read_csv(DATA_PATH(stock_name), index_col=0)
    df.index = pd.to_datetime(df.index, format="%Y-%m-%d %H:%M:%S")
    df = df[["close"]].rename(columns={"close":stock_name})
    
    ## End of Data
    eod_df = yf.download(stock_name.replace(".", "-"), start = "2021-01-23",end="2021-03-22")[["Close"]]
    eod_df = eod_df.rename(columns={"Close":stock_name})
    
    return df, eod_df

def get_exit_spred(df_quantile, exit_quantile, entry_spread, min_spread_thresh=0.45, upper = True):
    
    '''
    Parameters:
        1. df_quantile: pd.DataFrame
            Intra spread data frame for look_back_days
        
        2. exit_quantile: float
            Quantile spread to square off the position.
        
        3. entry_spread: float
            Threshold spread at which the trade will be taken
        
        4. min_spread_thresh: float
            Minimum quantile to which `exit_quantile` can be decreased/increased depending upon `upper`
        
        5. upper: bool
            if upper is True, means to calculate exit spread for upper quantile, else it is for lower quantile
        
    
    Returns:
        1. exit spread of a particular spread if abs(entry_spread - exit_spread) > min_entry_exit_spread_diff else
            it returns np.nan    
    '''
    
    while True:
        exit_spread = df_quantile.quantile(exit_quantile)
        spread_return = abs(entry_spread - exit_spread)

        if upper:
            if spread_return*1e4 >= config["min_entry_exit_spread_diff"]:
                return exit_spread
            
            elif exit_quantile < min_spread_thresh:
                return np.nan
            
            else:
                exit_quantile -= 0.05
        
        else:            
            if spread_return*1e4 >= config["min_entry_exit_spread_diff"]:
                return exit_spread
            
            elif exit_quantile > (1 - min_spread_thresh):
                return np.nan
            
            else:
                exit_quantile += 0.05
            


def entry_trade(df, timestamp, pair, type_="long"):
    '''
    Parameters:
        1. df: pd.DataFrame
            Data frame of the prices of the stocks
        
        2. timestamp: pd.Timestamp
            Timestamp at which the trade is being taken
        
        3. pair: list
            Stocks on which the trade will be taken
        
        4. type_: str
            if "long", assumes a long trade is being taken, else "short" trade is being taken
    
    Returns:
        1. long_price: float
            Slippage adjusted entry price of the long stock
        
        2. short_price: float
            Slippage adjusted entry price of the short stock
        
        3. long_symbol: str
            Name of the symbol on which long position is being taken.

        4. short_symbol: str
            Name of the symbol on which short position is being taken.
    '''

    if type_ == "short":
        long_price = df.loc[timestamp, pair[1]] * (1 + slippage_per_leg) # leg2. denominator
        short_price = df.loc[timestamp, pair[0]] * (1 - slippage_per_leg) # leg1, numerator
        long_symbol, short_symbol = pair[1], pair[0]
    
    elif type_ == "long":
        long_price = df.loc[timestamp, pair[0]] * (1 + slippage_per_leg) # leg1, numerator
        short_price = df.loc[timestamp, pair[1]] * (1 - slippage_per_leg) # leg2, denominator
        long_symbol, short_symbol = pair[0], pair[1]
    
    return long_price, short_price, long_symbol, short_symbol

def m2m(df, timestamp, long_price, short_price, long_symbol, short_symbol):
    
    '''
    Parameters:
        1. df: pd.DataFrame
            Data frame of the prices of the stocks
        
        2. timestamp: pd.Timestamp
            Timestamp at which to calculate the m2m of the trade
        
        3. long_price: float
            Price at which the long position was taken
        
        4. short_price: float
            Price at which the short position was taken
        
        5. long_symbol: str
            Name of stock with long position
        
        6. short_symbol: str
            Name of stock with short position
    
    Returns:
        1. M2M/PNL of the trade at the given timestamp.

    '''
    
    total_capital = long_price + short_price
    pnl_long = df.loc[timestamp, long_symbol] * (1-slippage_per_leg) - long_price
    pnl_short = short_price - df.loc[timestamp, short_symbol] * (1+slippage_per_leg)
    
    pnl = (pnl_long + pnl_short)/total_capital
    
    return pnl


m2m_dict = {}
for pair in pair_list:
    m2m_dict[tuple(pair)] = []
    
    df_stock_a, eod_stock_a = get_stock_data(pair[0])
    df_stock_b, eod_stock_b = get_stock_data(pair[1])
    
    # Merging the stock data
    pair_df = pd.merge(df_stock_a, df_stock_b, how="outer", left_index=True, right_index=True)
    
    # Calculating the spread of the pair
    eod_data = eod_stock_a.iloc[:,0]/eod_stock_b.iloc[:,0]
    eod_data.index = eod_data.index.astype(str)
    
    # Previous day spread is used as refernce for current day to calculate spread.
    eod_data_spread_dict = eod_data.shift().to_dict()
    
    ## Sloppy but no other way out
    # pair_df = pair_df.fillna(method="ffill")
    pair_df = pair_df.dropna()
    
    ###
    ## Removing first 10 minutes of maket noise in the data
    pair_df = pair_df.between_time("09:40", "16:00")
    intra_day_pair_spread = (pair_df.iloc[:,0]/pair_df.iloc[:,1]).to_frame()
    intra_day_pair_spread["prev_close"] = intra_day_pair_spread.index.map(lambda x: eod_data_spread_dict[str(x).split(" ")[0]])
    intra_day_pair_spread["change_in_spread"] = intra_day_pair_spread.iloc[:, 0]/intra_day_pair_spread.iloc[:, 1] - 1
    
    dates = sorted(list(set(intra_day_pair_spread.index.map(lambda x: str(x).split(" ")[0]))))
    dates = list(map(lambda x: dt.datetime.strptime(x, "%Y-%m-%d").date(), dates))
    
    for i in range(config["look_back_days"]+1, len(dates)):
        
        # Look back start and end date
        start = dates[i - config["look_back_days"] - 1]
        end = dates[i-1]
        
        # DataFrame to be used to calculate quantile of spread.
        df_quantile = intra_day_pair_spread.loc[start:end, "change_in_spread"]
        current_day_df = intra_day_pair_spread[intra_day_pair_spread.index.astype(str).str.startswith(str(dates[i]))]['change_in_spread']

        entry_exit_rule_dict = {}
        ignore_perc = []
        
        for x in config["threshold"]:
            
            # Upper quantile stats
            upper_quantile_entry = df_quantile.quantile(x)
            upper_quantile_exit = get_exit_spred(df_quantile, x - config["sq_thresh_diff"], upper_quantile_entry)
            upper_quantile_stop_loss = upper_quantile_entry + (upper_quantile_entry-upper_quantile_exit)
            
            if upper_quantile_exit == np.nan:
                ignore_perc.append(x)
            
            # Lower quantile stats
            lower_quantile_entry = df_quantile.quantile(1-x)
            lower_quantile_exit = get_exit_spred(df_quantile, 1 - (x - config["sq_thresh_diff"]), lower_quantile_entry, upper=False)
            lower_quantile_stop_loss = lower_quantile_entry - (lower_quantile_exit - lower_quantile_entry)
            
            if lower_quantile_exit == np.nan:
                ignore_perc.append(1-x)
            
            # entry_exit_rule_dict[x] = [upper_quantile_entry, upper_quantile_exit, upper_quantile_stop_loss]
            # entry_exit_rule_dict[1-x] = [lower_quantile_entry, lower_quantile_exit, lower_quantile_stop_loss]
            
            open_position = False
            for j in range(len(current_day_df)):
                    
                ts = current_day_df.index[j]
                
                ## Check Entry Position Logic
                if current_day_df[j] > upper_quantile_entry and not open_position and upper_quantile_exit is not np.nan:
                    long_price, short_price, long_symbol, short_symbol = entry_trade(pair_df, ts, pair, type_="short")
                    open_position = "short"
                    print("Short at", ts)
                
                elif current_day_df[j] < lower_quantile_entry and not open_position and lower_quantile_exit is not np.nan:
                    long_price, short_price, long_symbol, short_symbol = entry_trade(pair_df, ts, pair, type_="long")
                    open_position = "long"
                    print("Long at", ts)

                
                ## Check Exit Position
                if open_position == "short":
                    if current_day_df[j] <= upper_quantile_exit:
                        pnl = m2m(pair_df, ts, long_price, short_price, long_symbol, short_symbol)
                        m2m_dict[tuple(pair)].append([ts, pnl])
                        open_position = False
                        print("Sq Short", ts)
                    
                if open_position == "long":
                    if current_day_df[j] >= lower_quantile_exit:
                        pnl = m2m(pair_df, ts, long_price, short_price, long_symbol, short_symbol)
                        m2m_dict[tuple(pair)].append([ts, pnl])
                        open_position = False
                        print("Sq Long", ts)
                
                # Squaring off the position at end of day
                if open_position and ts.time() > config["sq_time"]:
                    pnl = m2m(pair_df, ts, long_price, short_price, long_symbol, short_symbol)
                    m2m_dict[tuple(pair)].append([ts, pnl])
                    print("Sq EOD", ts)

                    break

print()
## Plotting Daywise PNL
ls_ = []
for keys, items in m2m_dict.items():
    ls_.extend(items)
    print(keys, "Pnl(bps)",round((sum([x[1] for x in items])*1e4), 2))

df_pnl = pd.DataFrame(ls_, columns=["timestamp", "pnl"])
df_pnl = df_pnl.set_index("timestamp")
df_pnl = df_pnl.sort_index()
df_pnl["date"] = df_pnl.index.map(lambda x: str(x).split(" ")[0])
df_pnl = df_pnl.groupby("date").sum()
df_pnl["cumulative_pnl"] = df_pnl["pnl"].cumsum()
df_pnl["cumulative_pnl"].plot(legend=True)



