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
    

class DollarCostAvg(bt.Strategy):
    params = dict(
        monthly_cash = 1000,
        monthly_range= [20] # in which day to buy 
        )
    
    def __init__(self):
        ## additional
        self.order = None
        self.totalcost = 0
        self.cost_wo_broker = 0
        self.units = 0
        self.times_traded = 0
        
    def log(self, txt, dt = None):
        dt = dt or self.datas[0].datetime.date(0)
        print('%s, %s' %(dt.isoformat(), txt))
        
    
    def start(self):
        self.broker.set_fundmode(fundmode = True, fundstartval = 100.0)
        
        self.cash_start = self.broker.get_cash()
        self.val_start = 100.0
        
        # add a timer
        self.add_timer(
            when = bt.timer.SESSION_START,
            monthdays = [i for i in self.p.monthly_range],
            monthcarry = True,
        )

    
    def notify_timer(self, timer, when, *args):
        '''
        spored men tova moje da se izhicisti kato logika
        i da place-va order spored market price-a i tova 
        kolko moje da se kupi na opredeleniq den
        
        moje i da se napravi spored nai-niskite pazarni 
        ceni v meseca da cheatne i da nakupi za da se 
        vidi best case scenario (nishto che e nerealistichno)
        '''
        self.broker.add_cash(self.p.monthly_cash)
        
        target_value = self.broker.get_value() + self.p.monthly_cash - 10
        self.order_target_value(target = target_value)
        
        # print some additional info
        print("*." * 40)
        print(when.strftime("%Y-%m-%d"))
        print("Cash @ specific timer", round(self.broker.get_cash(), 2))
        print("*." * 40)
        print(" ")

    
    def notify_order(self, order):
        #last_executed_price = order.executed.price
        #self.purchase_prices.append(last_executed_price)
        
        if order.status in [order.Submitted, order.Accepted]:
            return # do nothing
        
        if order.status in [order.Completed]:
            if order.isbuy(): # want to log 
                self.log("BUY EXECUTED: Price: {}, Cost: {}, Comm: {}, Size: {}".format(
                    round(order.executed.price, 2),
                    round(order.executed.value, 2),
                    round(order.executed.comm, 2),
                    round(order.executed.size, 2)
                ))
                print("Cash available after purchasing:", round(self.broker.get_cash(), 2))
                print("")
                
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
        print('/*'*17, "DOLLAR_AVG_COST @ REGULAR INTERVALS", '/*'*17)
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
        
        # FROI
        # This result shows how much more (or less) your fund is worth compared to the original $100, 
        # but it doesn't express this as a percentage.

        # Really for simplicy interested in this value
        print("*" * 3, " Gross Return", "*" * 3 )
        print("Gross Return USD: ", round((value - self.totalcost), 2))


cerebro = bt.Cerebro()
cerebro.adddata(feed)
cerebro.addstrategy(DollarCostAvg)

# Broker info
cerebro.broker = bt.brokers.BackBroker(coc=True)
comminfo = FixedCommision()
cerebro.broker.addcommissioninfo(comminfo)
#cerebro.broker.set_cash(100)
cerebro.run()
cerebro.plot(style = "candlestick")