# Lab Heat Pump Control & Data Acquisition System with Borehole Heat Exchanger 

**[IN DEVELOPMENT]** A real-time monitoring, control, and data logging application for lab-scale heat pump test benches, powered by **Streamlit** and Python. 
An initiative by Institute of Subsurface Energy Systems (TU Clausthal).

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://bhe-hp.streamlit.app)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Overview

This repository will contain the software suite used to interface with the laboratory heat pump setup. It bridges hardware data acquisition (DAQ) units with an intuitive web UI built using Streamlit. 

Researchers can adjust operational parameters, monitor thermodynamic cycles in real time (e.g., $P$ - $h$ diagrams), and automatically log high-frequency test data.

### Key Features
* **Real-Time Telemetry:** Live plotting of temperature, pressure, mass flow rate, and power consumption.
* **Thermodynamic Modeling:** Dynamic $P$ - $h$ and $T$ - $s$ diagram generation using `CoolProp`.
* **Automated Logging:** Export standardized `.csv` test runs with experiment metadata.
* **Safety Protocols:** Automatic threshold monitoring with hardware shutdown alerts.
