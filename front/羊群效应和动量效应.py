import random 
import pandas as pd
import numpy as np
import statsmodels.formula as smFormula
import statsmodels.api as smApi
from operator import methodcaller
def initialize(context):
    # 定义行业指数 list 以便去股票
    g.indexList = ['399005.XSHE','399006.XSHE']
    # 定义全局参数值
    g.pastDay = 60# 过去 pastDay 日参数
    g.topK =10#topK 只股票
    g.herdSign = np.zeros((len(g.indexList),1))
    set_backtest()#3设置回测条件
 #每月判断一次羊群效应
    run_monthly(mainHerd, 1, time='before_open')
def set_backtest():
    set_option('use_real_price', True) #用真实价格交易
    log.set_level('order', 'error')
 
def before_trading_start(context):
    set_slip_fee(context) 
def set_slip_fee(context):
    set_slippage(FixedSlippage(0),type='mmf',ref='000012.XSHG') #货币基金滑点为0
    set_slippage(FixedSlippage(0.02),type='stock') # 股票交易滑点0.02
    set_order_cost(OrderCost(open_tax=0, close_tax=0.000, open_commission=0.0000, close_commission=0.0000, close_today_commission=0, min_commission=0), type='stock', ref='000012.XSHG')
    # 根据不同的时间段设置手续费,货币基金收费为0，股票为真实手续费
    dt=context.current_dt
    if dt>datetime.datetime(2013,1, 1):
        set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, close_commission=0.0003, close_today_commission=0, min_commission=5), type='stock')
    elif dt>datetime.datetime(2011,1, 1):
        set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.001, close_commission=0.001, close_today_commission=0, min_commission=5), type='stock')
    elif dt>datetime.datetime(2009,1, 1):
        set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.002, close_commission=0.002, close_today_commission=0, min_commission=5), type='stock')
    else:
        set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.003, close_commission=0.003, close_today_commission=0, min_commission=5), type='stock')

# 计算相对强弱 RPS 值
def calRPS(stocks,curDate1,preDate2):
    try:
    # 初始化参数信息
        numStocks = len(stocks)
        rankValue = []
 # 计算涨跌幅
        for security in stocks:
            lastDf = get_price(security, start_date = preDate2, end_date = curDate1, frequency = '1d', fields = 'close')
            lastClosePrice = float(lastDf.iloc[-1])
            firstClosePrice = float(lastDf.iloc[0])
            errCloseOpen = [(lastClosePrice -firstClosePrice)/firstClosePrice]
            rankValue += errCloseOpen
 # 根据涨跌幅排名
        rpsStocks = {'code':stocks,'rankValue':rankValue}
        rpsStocks = pd.DataFrame(rpsStocks)
        rpsStocks = rpsStocks.sort('rankValue',ascending = False)
        stocks = list(rpsStocks['code'])
        rankValue = list(rpsStocks['rankValue'])
 # 计算 RPS 值
        rpsValue = [99 - (100 * float(i)/numStocks) for i in range(numStocks)]
        rpsStocks = {'code':stocks,'rpsValue':rpsValue,'rankValue':rankValue}
        rpsStocks = pd.DataFrame(rpsStocks)
        return rpsStocks
    except:
        print('Turn to modify code in function "calRPS"')
        # 计算羊群效应
def mainHerd(context):
    # 获取全局参数
    indexList = g.indexList
    pastDay = g.pastDay
    curDate1 = context.current_dt.date()+datetime.timedelta(days = -1)
    preDate = curDate1 + datetime.timedelta(days = -pastDay)
    curDate1 = str(curDate1);preDay = str(preDate)
    returnArr = g.herdSign
    IndustryGain= g.herdSign
    for i,eachIndex in enumerate(indexList):
        IndustryGain[i]=calIndustryGain(eachIndex,preDate,curDate1)
    if IndustryGain[i]>0.01:
        returnArr[i] = calHerdSign(eachIndex,pastDay,curDate1,preDate)
    else:
        returnArr[i]=0
    g.herdSign = returnArr
#交易函数 每天运行一次
def handle_data(context, data):
    # 初始化参数
    indexList = g.indexList
    topK = g.topK
    herdSign = g.herdSign
    stocks = []
    # 计算日期参数
    pastDay = g.pastDay
    curDate1 = context.current_dt.date()+datetime.timedelta(days = -1)
    curDate = context.current_dt.date()
    curDate = str(curDate)
    preDate = curDate1+ datetime.timedelta(days = -pastDay)
    preDate = str(preDate)
    preDate2 = curDate1 + datetime.timedelta(days = -1)
    preDate2 = str(preDate2)
    curDate1 = str(curDate1)
 # 根据羊群效应选取股票
    for i,eachIndex in enumerate(indexList):
        if herdSign[i] == 1:
            try:
                oriStocks = get_index_stocks(eachIndex,curDate1)
                rpsStocks = calRPS(oriStocks,curDate1,preDate2)
                stocks += list(rpsStocks[:topK]['code'])
            except:
                oriStocks = get_index_stocks(eachIndex,curDate1)
                stocks+=filtGain(oriStocks,preDate2,curDate1)
    # 筛选股票：排除重复的，持股 topK 只
    stocks = list(set(stocks))
    numStocks = len(stocks)
    if numStocks > topK:
        stocks=filtGain(stocks,preDate2,curDate1)
    else:
        pass
    numStocks = len(stocks)
    # 根据候选池买卖股票
    order_target('000012.XSHG',0) # 卖出货币基金操作
    #卖出操作：持有股票近10天收盘价格平均值小于近30天股票收盘价格平均值，则卖出。
    for security in context.portfolio.positions.keys():
        ma10 = data[security].mavg(10,'close')
        ma30 = data[security].mavg(30,'close')
        if ma10<ma30:
            order_target(security,0)
        else:
            continue
    # 买入操作：股票池中股票1天收盘价格平均值大于近3天股票收盘价格平均值，则买入。
    cash = context.portfolio.available_cash 
    for security in stocks:
        ma1 = data[security].mavg(1,'close')
        ma3 = data[security].mavg(3,'close')
        if ma1>ma3:
            # 获取股票基本信息：是否停牌、是否 ST,持股头寸、股价等
            currentData = get_current_data()
            pauseSign = currentData[security].paused
            STInfo = get_extras('is_st',security,start_date=preDate,end_date=curDate)
            STSign = STInfo.iloc[-1]
            stocksAmount = context.portfolio.positions[security].amount
            stocksPrice = data[security].price
            cash = context.portfolio.available_cash
            if not pauseSign and not STSign.bool():
                buyAmount = int((cash / topK) / stocksPrice)
                order(security,buyAmount)
            else:
                order('000012.XSHG', int(cash / topK))
        else:
                order('000012.XSHG', int(cash / topK))
    cash = context.portfolio.available_cash
    order_value('000012.XSHG', cash) #剩余资金买入货币基金
    log.info("Buying %s" % ('000012.XSHG')) 
 
# 根据涨幅筛选股票
def filtGain(stocks,preDate2,curDate1):
    numStocks = len(stocks)
    rankValue2 = []
    topK=g.topK
    # 计算涨跌幅
    for security in stocks:
        stocksPrice2 = get_price(security, start_date = preDate2, end_date = curDate1, frequency = '1d', fields = 'close')
        if len(stocksPrice2)!=0:
            errCloseOpen2 = [(float(stocksPrice2.iloc[-1]) -float(stocksPrice2.iloc[0])) / float(stocksPrice2.iloc[0])]
            rankValue2 += errCloseOpen2
        else:
            rankValue2 += [0]
 # 根据涨跌幅排名
    filtStocks1 = {'code':stocks,'rankValue':rankValue2}
    filtStocks1 = pd.DataFrame(filtStocks1)
    filtStocks1 = filtStocks1.sort('rankValue',ascending = False)
    filtStocks1 = filtStocks1.head(topK)
    filtStocks1 = list(filtStocks1['code'])
    return filtStocks1
# 计算行业涨幅
def calIndustryGain(indexss,preDate,curDate1):
    stocks=get_index_stocks(indexss,curDate1)
    gainIndex = 0
    try:
        for security in stocks:
            stocksPrice = get_price(security, start_date = preDate, end_date = curDate1, frequency = '1d', fields = 'close')
            if len(stocksPrice) != 0:
                gainIndex += (float(stocksPrice.iloc[-1]) -
float(stocksPrice.iloc[0])) / float(stocksPrice.iloc[0])
            else:
                continue
        if len(stocks)!=0:
            a=gainIndex/len(stocks)
        else:
            a=0
    except:
        a=0
    return a
# 判断：是否存在羊群效应
def calHerdSign(index,pastDay,curDate1,preDate):
    try:
     # 获取指数 pastDay 内的价格
        indexPrice = get_price(index,start_date = preDate, end_date = curDate1, frequency = '1d',fields = ['close'])
    # 获取不同日期的 Rmt
    # 初始化存储数组
        stockPeInfo = indexPrice
        stockPeInfo['Rmt'] = np.nan
        stockPeInfo['Rmt2'] = np.nan
        dateInfo = (stockPeInfo.T).columns
    # 计算 Rmt
        valid_stocks = 0
        stockPE = 0
        peIndex = 0
        dateInfo = dateInfo.map(methodcaller('date'))
        for days in dateInfo:
        # 获取指数内的股票
            stocks = get_index_stocks(index,days)
            numStocks = len(stocks)
            for security in stocks:
                peInfo = get_fundamentals(query(valuation.pe_ratio).filter(valuation.code.in_([security])), date = days)
                if not peInfo.empty:
                    pe_ratio = peInfo['pe_ratio'].iloc[0]
                    if pd.notna(pe_ratio) and pe_ratio > 0:  # 过滤无效PE
                        stockPE += float(pe_ratio)
                        valid_stocks += 1
                    continue
        if valid_stocks > 0:
            peIndex = stockPE / valid_stocks  # 使用有效股票数作为分母
            stockPeInfo.loc[days, 'Rmt'] = abs(peIndex)
            stockPeInfo.loc[days, 'Rmt2'] = peIndex ** 2
 # 重置参数
            stockPE = 0
            peIndex = 0
        formula = 'close~Rmt+Rmt2';formula = formula.encode('ascii')
        olsResult = smFormula.api.ols(formula = formula,data=stockPeInfo).fit()
        coef = olsResult.params.loc['Rmt2']
        pvalues = olsResult.pvalues.loc['Rmt2']
        if pvalues < 0.15 and coef < 0:
            return 1
        else:
            return 0
    except:
        print('Turn to modify code in function "calHerdSign"')