# LocalAlpha

**The Privacy-First Frontend for QuantConnect LEAN**

[![Release](https://img.shields.io/github/v/release/LocalAlpha-io/localalpha-releases)](https://github.com/LocalAlpha-io/localalpha-releases/releases)

LocalAlpha is a local desktop dashboard that allows you to visualize backtests, debug logs, and analyze trade performance without cloud uploads. Engineered for performance and privacy, it serves as the visualization layer for your local LEAN CLI workflows.

## 🚀 Overview

LocalAlpha is designed to fit seamlessly into your existing local development loop. It reads standard JSON output files from the LEAN engine and provides institutional-grade analytics on your desktop.

**100% Local & Private** Your strategy code and results never leave your machine. LocalAlpha runs entirely offline, making it safe for proprietary institutional algorithms. No telemetry, no "cloud sync", no leaks.

## ✨ Features

- **Interactive Charts**: High-performance, zoomable canvas charts for equity curves, drawdowns, and benchmark comparisons.
- **Advanced Metrics**: Instant local recalculation of Sharpe, Sortino, Calmar, and PSR ratios.
- **Trade X-Ray**: Drill down into every execution. Use MAE (Maximum Adverse Excursion) and MFE scatter plots to optimize stop-losses and take-profit levels with surgical precision.
- **Log Explorer**: Virtualized, regex-powered search capable of handling gigabyte-sized log files with zero lag.
- **Reality Check**: Reconcile your backtests with live trading results. Detect slippage, latency, and execution errors by matching trades across result files.
- **Optimization Heatmaps**: Visualize parameter stability to avoid overfitting.
- **Portfolio Intelligence**: Analyze correlations, sector exposure, and rolling beta across multiple strategies.

## 🛠 How It Works

1.  **Run Backtest**: Execute your strategy locally using the LEAN CLI as usual.
2.  **Auto-Ingest**: LocalAlpha watches your output folder. As soon as `result.json` appears, the dashboard updates instantly.
3.  **Deep Dive**: Analyze metrics, inspect trades, and debug logs without leaving your desktop.

## 📥 Download

Download the latest version for your operating system from the [Releases Page](../../releases).

| Platform | Support |
| :--- | :--- |
| **macOS** | Universal Binary (Apple Silicon & Intel) |
| **Windows** | Windows 10/11 Installer (.msi) |
| **Linux** | AppImage / Deb (Ubuntu/Debian based) |

## 🧩 Compatibility

- **LEAN CLI**: Fully compatible with standard JSON output.
- **Live Trading**: Supports real-time monitoring by tailing live deployment result files.

## 📄 License

LocalAlpha is a commercial product with a free trial and a Professional License for advanced features. See [localalpha.io](https://localalpha.io/) for pricing details.

---
*LocalAlpha is not affiliated with QuantConnect Corporation.*
