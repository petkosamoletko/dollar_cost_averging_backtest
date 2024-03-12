# imports
import datetime
import math
import random
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt 
from pandas_datareader import data as pdr
import backtrader as bt
import yfinance as yf
from datetime import timedelta
yf.pdr_override()


def get_stock_data(stock, timeframe_years):
    endDate = datetime.datetime.now()
    delta = datetime.timedelta(365 * timeframe_years)
    startDate = endDate - delta
    stockData = pdr.get_data_yahoo(stock, startDate, endDate)
    
    startDate = stockData.index[0]
    endDate = stockData.index[-1]
    
    return stockData, startDate, endDate 


df, startDate, endDate = get_stock_data("VOO", 10)
feed = bt.feeds.PandasData(dataname = df)
print("Start Date:", startDate.strftime("%B %d, %Y, %I:%M:%S %p"))
print("End Date:", endDate.strftime("%B %d, %Y, %I:%M:%S %p"))

class FixedCommision(bt.CommInfoBase):
    '''
    may need some tweaking
    if having per trade comission
    '''
    paras = (
    ("commision", 10),
    ("stocklike", True),
    ("commtype", bt.CommInfoBase.COMM_FIXED)
    )
    
    def _getcommission(self, size, price, pseudoexec):
        return self.p.commission
    
log_prices = {}
year_month = []
for i in df.index:
    date = (i.year, i.month)
    year_month.append(date)

for i in year_month:
    if i is not log_prices:
        log_prices[i] = []

for year, month in log_prices.keys():
    for i in df.index:
        if (i.month == month) and (i.year == year):
            # backlogging checks
            #print("")
            #print(i.day)
            #print(df.loc[i]["Close"])
            #print(df.loc[i])
            dict_value = (i.day, df.loc[i]["Close"])
            log_prices[(year, month)].append(dict_value)


trading_days = {}
for i in log_prices:
    #print(len(log_prices[i]))
    #print('*')
    rand_day = random.randrange(0, len(log_prices[i]))
    #print(rand_day)
    #print('*')
    prices = log_prices[i]
    #print(log_prices[i][rand_day])
    #sorted_prices = sorted(prices, key = lambda x: x[1])
    #print(i, "prices", sorted_prices[:3])
    #trading_days[i] = sorted_prices[0]
    trading_days[i] = log_prices[i][rand_day] 


timestamps = []
for year, month in trading_days:
    day = trading_days[(year, month)][0]
    timestamps.append(datetime.datetime(year, month, day))

timestamps = sorted(timestamps)
adjusted_timestamps = [timestamp - timedelta(days=1) for timestamp in timestamps]
# ideal days to trade on - backlogging
print("Best days to trade at")
print(timestamps)
print(" ")
#print(adjusted_timestamps)

class SelfMadeStrat(bt.Strategy):
    params = dict(
        monthly_cash = 1000
        )
    
    def __init__(self):
        ## additional
        self.order = None
        self.totalcost = 0
        self.cost_wo_broker = 0
        self.units = 0
        self.times_traded = 0
        self.last_cash_added_month = None
        
        global adjusted_timestamps
        self.specific_dates = [dt.date() for dt in adjusted_timestamps]

    def log(self, txt, dt = None):
        dt = dt or self.datas[0].datetime.date(0)
        print('%s, %s' %(dt.isoformat(), txt))


    def start(self):
        self.broker.set_fundmode(fundmode = True, fundstartval = 100.0)

        self.cash_start = self.broker.get_cash()
        self.val_start = 100.0

        # add a timer - freq of trades in terms of dates 
        self.add_timer(
            when=bt.Timer.SESSION_START,
            weekdays = [0, 1, 2, 3, 4, 5, 6],
            weekcarry = True
        )


    def notify_timer(self, timer, when, *args):
        current_date = self.datas[0].datetime.date(0)
        current_month = current_date.month
        
        if self.last_cash_added_month != current_month:
            self.broker.add_cash(self.p.monthly_cash)
            print(" ")
            print(" PAY DAY ")
            print(" * " * 10)
            print(f"Cash added on {current_date}: {self.p.monthly_cash}")
            print("Cash available:", self.broker.get_cash())
            self.last_cash_added_month = current_month
 
        if current_date in self.specific_dates:
            current_cash = self.broker.get_cash()
            closing_p = self.datas[0].close[0]
            self.get_amount = math.floor(current_cash/closing_p)
            if self.get_amount > 0:
                self.buy(size = self.get_amount)
        else:
            print(current_date, "No activity")

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return # do nothing

        if order.status in [order.Completed]:
            if order.isbuy(): # want to log 
                #print("Target amount to get:", self.get_amount)
                print(" ")
                print("PURCHASE DAY")
                print(" * " * 10)
                self.log("BUY EXECUTED: Price: {}, Cost: {}, Comm: {}, Size: {}".format(
                    round(order.executed.price, 2),
                    round(order.executed.value, 2),
                    round(order.executed.comm, 2),
                    round(order.executed.size, 2)
                ))
                print("Cash available after purchasing:", round(self.broker.get_cash(), 2))
                print(" * " * 10)
            self.units += order.executed.size
            self.totalcost += order.executed.value + order.executed.comm
            self.cost_wo_broker += order.executed.value
            self.times_traded += 1

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log("ORDER CANCLED/MARGIN/REJECT => NA")
            print(order.status, [order.Canceled, order.Margin, order.Rejected])

        self.order = None

    def stop(self):
        # calculate actual return
        self.roi = (self.broker.get_value() / self.cash_start) - 1
        self.froi = (self.broker.get_fundvalue() - self.val_start)
        value = self.datas[0].close * self.units + self.broker.get_cash()
        print('/*'*13, "DOLLAR_AVG_COST @ RANDOM TIMES OF THE MONTH", '/*'*13)
        print("")


        print("Time in Market: Years", round((((endDate - startDate).days)/ 365), 2)) 
        print("# Time in market: ", round((self.times_traded), 2))
        print("# Total stock count: ", round((self.units), 2))
        print("Purchase Value (+ Cash within Broker): ", round((value), 2))
        print("Purchase Cost: ", round((self.totalcost), 2))
        #print("Gross Return: ", round((value - self.totalcost), 2))
        print("Gross %: ", round ((((value/self.totalcost) - 1) * 100), 2))
        print("ROI %:", round((100 * self.roi), 2))
        #print("Fund Value: ", round((self.froi), 2))

        delta = endDate - startDate                     
        annual_base = 1 + self.froi
        n = 365 / delta.days
        annual_froi = (annual_base ** n) - 1
        print("Annualized: %", round((annual_froi * 100), 2))


        # Really for simplicy interested in this value
        print("*" * 3, " Gross Return", "*" * 3 )
        print("Gross Return USD: ", round((value - self.totalcost), 2))

if __name__ == '__main__':
    cerebro2 = bt.Cerebro()
    cerebro2.adddata(feed)
    cerebro2.addstrategy(SelfMadeStrat)

    # Broker info
    cerebro2.broker = bt.brokers.BackBroker(coc=True)
    comminfo = FixedCommision()
    cerebro2.broker.addcommissioninfo(comminfo)

    cerebro2.run()

    cerebro2.plot(style = "candlestick")






