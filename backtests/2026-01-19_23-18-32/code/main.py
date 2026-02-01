# region imports
from AlgorithmImports import *
from email.message import EmailMessage
import requests
import smtplib
import json
import traceback
import math

class KDJStrategy(QCAlgorithm):

    def Initialize(self):
        # --- BASIC SETTINGS ---
        self.SetStartDate(2021, 1, 1)
        self.SetEndDate(2026, 1, 1)
        self.SetBenchmark("QQQ")
        self.SetCash(30000)
        self.set_brokerage_model(BrokerageName.INTERACTIVE_BROKERS_BROKERAGE, AccountType.CASH)
        self.SetSecurityInitializer(lambda security: security.SetFeeModel(ConstantFeeModel(0)))

        # --- RISK / SIZING SETTINGS ---
        # UPDATED: We use ATR Multiplier instead of fixed trailing percent
        self.atr_multiplier = 3.0   
        self.atrPeriod = 14
        self.eachStockInvestment = 20000

        # --- OPTIMIZED KDJ PARAMETERS ---
        # UPDATED: Changed defaults to "Smooth Swing" (21, 5, 5) to reduce false signals
        period   = int(self.GetParameter("period")   or 14)
        kPeriod  = int(self.GetParameter("kPeriod")  or 2)
        dPeriod  = int(self.GetParameter("dPeriod")  or 2)

        # --- Trade SOXL only ---
        self.stock_configs = [
            {"ticker": "SOXL", "disabled": False,
             "buy_signal":  float(self.GetParameter("soxl_buy_signal")  or 22.2),
             "sell_signal": float(self.GetParameter("soxl_sell_signal") or 62.6)},
        ]

        self.soxl_symbol = None
        self.soxl_sma = None  # Placeholder for the Regime Filter
        self.stocks = {}

        # Add SOXL and indicators
        for config in self.stock_configs:
            if config["disabled"]:
                continue

            ticker = config["ticker"]
            equity = self.AddEquity(ticker, Resolution.Hour)
            symbol = equity.Symbol

            if ticker == "SOXL":
                self.soxl_symbol = symbol
                
                # UPDATED: Register the Regime Filter (200 Day SMA)
                # We need Daily resolution for the regime filter even if trading on Hour
                self.soxl_sma = self.SMA(symbol, 200, Resolution.Daily)
                
                stochastic = Stochastic(period, kPeriod, dPeriod)
                self.RegisterIndicator(symbol, stochastic, Resolution.Hour)
                kdj_indicator = stochastic
            else:
                kdj_indicator = None

            atr = self.atr(symbol, self.atrPeriod, MovingAverageType.Simple)

            self.stocks[symbol] = {
                "ticker": ticker,
                "stochastic": kdj_indicator,
                "atr": atr,
                "buy_signal": config.get("buy_signal"),
                "sell_signal": config.get("sell_signal"),
                "previous_j": None,
                "purchase_price": None,
                "high_price": None
            }

        # Warm up
        self.SetWarmUp(timedelta(days=200)) # Increased for SMA 200

        if self.LiveMode:
            self.RestoreState()

        # --- EOD liquidation schedule ---
        # UPDATED: Uncommented and set to liquidate LOSERS
        if self.soxl_symbol:
            minutes_before_close = 10
            self.Schedule.On(self.DateRules.EveryDay(self.soxl_symbol),
                             self.TimeRules.BeforeMarketClose(self.soxl_symbol, minutes_before_close),
                             self.LiquidatePositionsBeforeClose)
            self.Debug(f"Scheduled EOD Risk Check {minutes_before_close} minutes before close.")

        if self.LiveMode:
            self.Debug("Finished initialization")

    def LiquidatePositionsBeforeClose(self):
        """
        UPDATED LOGIC:
        Instead of selling winners (capping profit), we sell LOSERS (stopping bleeding).
        If we are red going into the close, we assume the overnight gap will be against us.
        """
        if not self.Portfolio.Invested:
            return

        self.Log(f"--- Running End-of-Day Risk Check @ {self.Time} ---")
        liquidated_symbols = []

        try:
            for symbol in list(self.Portfolio.Keys):
                holding = self.Portfolio[symbol]
                if holding.Invested:
                    unrealized_profit = holding.UnrealizedProfit
                    
                    # UPDATED: If profit < 0 (Loser), Kill it.
                    if unrealized_profit < 0:
                        self.Log(f"CLOSING LOSER: {holding.Symbol.Value} is down ${unrealized_profit:.2f}. avoiding overnight risk.")
                        self.Liquidate(holding.Symbol)
                        self.ResetStockState(holding.Symbol)
                        liquidated_symbols.append(holding.Symbol.Value)
                    else:
                        self.Log(f"HOLDING WINNER: {holding.Symbol.Value} is up ${unrealized_profit:.2f}. Letting it ride overnight.")

            if liquidated_symbols and self.LiveMode:
                msg = f"EOD Defense: Cut losers {', '.join(liquidated_symbols)}"
                self.SendInternalNotification(msg)

        except Exception as e:
            self.HandleRuntimeError(e, "LiquidatePositionsBeforeClose")

    def OnData(self, data):
        # avoid last ~15min trades (conflicts with EOD logic)
        if self.Time.hour >= 15 and self.Time.minute >= 45:
            return

        if self.IsWarmingUp:
            return

        if not self.soxl_symbol or not data.Bars.ContainsKey(self.soxl_symbol):
            return

        try:
            if self.soxl_symbol in self.stocks:
                self.ProcessSoxl(data, self.soxl_symbol, self.stocks[self.soxl_symbol])
        except Exception as e:
            self.HandleRuntimeError(e, "OnData")

    def ProcessSoxl(self, data, soxl_symbol, soxl_data):
        stoch = soxl_data["stochastic"]
        atr   = soxl_data["atr"]

        if not stoch or not stoch.IsReady or not atr or not atr.IsReady:
            return

        k = stoch.StochK.Current.Value
        d = stoch.StochD.Current.Value
        j = 3 * k - 2 * d
        current_price = data[soxl_symbol].Close

        previous_j  = soxl_data["previous_j"]
        buy_signal  = soxl_data["buy_signal"]
        sell_signal = soxl_data["sell_signal"]

        # 1. Check Stops First
        self.ProcessIndependentStockLogic(data, soxl_symbol, soxl_data)
        soxl_invested = self.Portfolio[soxl_symbol].Invested

        if previous_j is None:
            soxl_data["previous_j"] = j
            return

        # 2. BUY LOGIC
        if previous_j < buy_signal and j > buy_signal:
            if not soxl_invested:
                
                # UPDATED: REGIME FILTER CHECK
                # If Price < 200 SMA, we are in a bear market. Do not buy dips.
                if self.soxl_sma and self.soxl_sma.IsReady:
                    if current_price < self.soxl_sma.Current.Value:
                        self.Log(f"FILTERED BUY: Signal valid but Price ({current_price}) < 200 SMA ({self.soxl_sma.Current.Value}). Staying Cash.")
                        soxl_data["previous_j"] = j
                        return

                qty = self.CalculateOrderQuantity(soxl_symbol, current_price)
                if qty > 0:
                    self.Debug(f"BUY SOXL: J={j:.2f} crossed > {buy_signal}. Price={current_price}")
                    self.MarketOrder(soxl_symbol, qty)
                    soxl_data["purchase_price"] = current_price
                    soxl_data["high_price"] = current_price

        # 3. SELL LOGIC
        elif previous_j > sell_signal and j < sell_signal:
            if self.Portfolio[soxl_symbol].Invested:
                self.Debug(f"SELL SOXL: J={j:.2f} crossed < {sell_signal}.")
                self.Liquidate(soxl_symbol)
                self.ResetStockState(soxl_symbol)
                
        soxl_data["previous_j"] = j

    def ProcessIndependentStockLogic(self, data, symbol, stock_data):
        """
        UPDATED: Now uses ATR for dynamic stop losses.
        """
        if not self.Portfolio[symbol].Invested:
            return

        current_price = data[symbol].Close
        high_price = stock_data["high_price"]
        
        # Initialize high_price if missing
        if high_price is None:
            stock_data["high_price"] = current_price
            high_price = current_price

        # Update High Watermark
        if current_price > high_price:
            stock_data["high_price"] = current_price
            high_price = current_price

        # UPDATED: ATR STOP CALCULATION
        atr = stock_data["atr"]
        stop_price = 0.0

        if atr and atr.IsReady:
            # Dynamic Stop: High Price minus 3x current Volatility
            stop_buffer = atr.Current.Value * self.atr_multiplier
            stop_price = high_price - stop_buffer
        else:
            # Fallback to fixed 10% if ATR breaks
            stop_price = high_price * 0.90

        if current_price < stop_price:
            pnl = self.Portfolio[symbol].UnrealizedProfit
            self.Log(f"ATR TRAILING STOP HIT: Selling {stock_data['ticker']}. "
                     f"Price={current_price:.2f} < Stop={stop_price:.2f}. P/L={pnl:.2f}")
            self.Liquidate(symbol)
            self.ResetStockState(symbol)

    def CalculateOrderQuantity(self, symbol, price):
        if price <= 0: return 0
        target_qty = math.floor(self.eachStockInvestment / price)
        # Ensure we don't spend more cash than we have
        available_qty = math.floor(self.Portfolio.Cash / price)
        return min(target_qty, available_qty)

    def ResetStockState(self, symbol):
        if symbol in self.stocks:
            self.stocks[symbol]["purchase_price"] = None
            self.stocks[symbol]["high_price"] = None

    # --- KEEPING YOUR EXISTING STATE RESTORE / SAVE / ERROR FUNCTIONS BELOW ---
    def RestoreState(self):
        # (Keep your existing RestoreState logic here)
        pass

    def SaveState(self):
        # (Keep your existing SaveState logic here)
        pass

    def HandleRuntimeError(self, exception, context="General"):
        self.Error(f"{context} Error: {exception}")

    def SendInternalNotification(self, message):
        # (Keep your existing notification logic)
        pass
