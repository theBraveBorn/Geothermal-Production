import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go

try:
    from CoolProp.CoolProp import PropsSI
except ImportError:
    st.error("CoolProp library not found. Please install it using `pip install CoolProp`.")
    st.stop()

# Page configuration
st.set_page_config(
    page_title="Enhanced Geothermal Production",
    page_icon="🔥",
    layout="wide"
)

st.title(" Heat Pump Cycle & Coaxial Borehole Heat Exhanger Analysis")
st.markdown("Interactively analyze heat pump cycles with a Coaxial BHE")

# Sidebar Controls
st.sidebar.header("Navigation")
app_mode = st.sidebar.radio(
    "Select Feature",
    ["Heat Pump Analysis", "Coaxial BHE (Coming Soon)", "System Monitor (Coming Soon)"]
)
if app_mode == "Heat Pump Analysis":
    refrigerant = st.sidebar.selectbox(
        "Select Refrigerant",
        ["R134a", "R410A", "R32", "R290", "R1234yf", "R717"],
        index=0
    )

    # Temperature limits based on refrigerant
    t_evap_c = st.sidebar.slider("Evaporating Temperature (°C)", -30.0, 20.0, -5.0, 1.0)
    t_cond_c = st.sidebar.slider("Condensing Temperature (°C)", 25.0, 75.0, 45.0, 1.0)

    if t_evap_c >= t_cond_c:
        st.sidebar.error("Evaporating temperature must be lower than Condensing temperature!")
        st.stop()

    superheat_k = st.sidebar.slider("Superheating (K)", 0.0, 20.0, 5.0, 0.5)
    subcooling_k = st.sidebar.slider("Subcooling (K)", 0.0, 15.0, 3.0, 0.5)
    eta_is = st.sidebar.slider("Compressor Isentropic Efficiency (%)", 50, 100, 75, 1) / 100.0
    heating_capacity_kw = st.sidebar.number_input("Heating Demand / Capacity (kW)", value=10.0, step=1.0)

    st.sidebar.header("2. Sensitivity Analysis Mode")
    sens_var = st.sidebar.selectbox(
        "Vary Parameter for Sensitivity Chart",
        ["Evaporating Temperature", "Condensing Temperature", "Compressor Efficiency", "Superheating"]
    )

    # Thermodynamic Calculation Helper
    def get_cycle_points(ref, t_evap, t_cond, sh, sc, eff_is):
        # Convert temperatures to Kelvin
        T_evap_K = t_evap + 273.15
        T_cond_K = t_cond + 273.15

        # Pressures (Pa)
        P_evap = PropsSI('P', 'T', T_evap_K, 'Q', 1, ref)
        P_cond = PropsSI('P', 'T', T_cond_K, 'Q', 0, ref)

        # Point 1: Compressor Inlet (Evaporator Outlet with Superheat)
        T1_K = T_evap_K + sh
        h1 = PropsSI('H', 'P', P_evap, 'T', T1_K, ref)  # J/kg
        s1 = PropsSI('S', 'P', P_evap, 'T', T1_K, ref)  # J/kg-K

        # Point 2s: Ideal Compressor Outlet
        h2s = PropsSI('H', 'P', P_cond, 'S', s1, ref)

        # Point 2: Actual Compressor Outlet
        h2 = h1 + (h2s - h1) / eff_is

        # Point 3: Condenser Outlet (with Subcooling)
        T3_K = T_cond_K - sc
        h3 = PropsSI('H', 'P', P_cond, 'T', T3_K, ref)

        # Point 4: Expansion Valve Outlet (Isenthalpic Expansion)
        h4 = h3

        return {
            'P_evap_bar': P_evap / 1e5,
            'P_cond_bar': P_cond / 1e5,
            'h1_kj': h1 / 1000,
            'h2_kj': h2 / 1000,
            'h3_kj': h3 / 1000,
            'h4_kj': h4 / 1000,
            'q_cond_kj': (h2 - h3) / 1000,  # Specific heating effect (kJ/kg)
            'q_evap_kj': (h1 - h4) / 1000,  # Specific cooling effect (kJ/kg)
            'w_comp_kj': (h2 - h1) / 1000   # Specific compressor work (kJ/kg)
        }



    # Execute Primary Calculation
    cycle = get_cycle_points(refrigerant, t_evap_c, t_cond_c, superheat_k, subcooling_k, eta_is)

    # Key Performance Indicators
    cop_heating = cycle['q_cond_kj'] / cycle['w_comp_kj']
    cop_cooling = cycle['q_evap_kj'] / cycle['w_comp_kj']
    mass_flow_rate = heating_capacity_kw / cycle['q_cond_kj']  # kg/s
    compressor_power_kw = mass_flow_rate * cycle['w_comp_kj']

    # Display Metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Heating COP", f"{cop_heating:.2f}")
    col2.metric("Compressor Power", f"{compressor_power_kw:.2f} kW")
    col3.metric("Mass Flow Rate", f"{mass_flow_rate * 3600:.1f} kg/h")
    col4.metric("Specific Work", f"{cycle['w_comp_kj']:.1f} kJ/kg")

    # Tabs Layout
    tab1, tab2 = st.tabs(["📉 P-h Diagram", "📊 Sensitivity Analysis"])

    with tab1:
        # 1. Build Saturation Dome Data
        T_crit_K = PropsSI('Tcrit', refrigerant)
        T_min_K = PropsSI('Tmin', refrigerant)
    
        # Generate saturation points up to near critical temperature
        T_sat_range = np.linspace(max(T_min_K + 1, 220), T_crit_K - 0.5, 120)
    
        h_fluid = []
        h_gas = []
        p_sat = []
    
        for T_sat in T_sat_range:
            try:
                p_sat.append(PropsSI('P', 'T', T_sat, 'Q', 0, refrigerant) / 1e5) # bar
                h_fluid.append(PropsSI('H', 'T', T_sat, 'Q', 0, refrigerant) / 1000) # kJ/kg
                h_gas.append(PropsSI('H', 'T', T_sat, 'Q', 1, refrigerant) / 1000)   # kJ/kg
            except:
                pass

        fig = go.Figure()

        # Plot Liquid Saturation Line
        fig.add_trace(go.Scatter(
            x=h_fluid, y=p_sat, mode='lines',
            name='Saturated Liquid', line=dict(color='blue', width=2)
        ))

        # Plot Vapor Saturation Line
        fig.add_trace(go.Scatter(
            x=h_gas, y=p_sat, mode='lines',
            name='Saturated Vapor', line=dict(color='red', width=2)
        ))

        # Cycle States Loop (1 -> 2 -> 3 -> 4 -> 1)
        cycle_h = [cycle['h1_kj'], cycle['h2_kj'], cycle['h3_kj'], cycle['h4_kj'], cycle['h1_kj']]
        cycle_p = [cycle['P_evap_bar'], cycle['P_cond_bar'], cycle['P_cond_bar'], cycle['P_evap_bar'], cycle['P_evap_bar']]

        # Plot Cycle Trajectory
        fig.add_trace(go.Scatter(
            x=cycle_h, y=cycle_p, mode='lines+markers+text',
            name='Heat Pump Cycle',
            text=['State 1 (Inlet)', 'State 2 (Outlet)', 'State 3 (Condenser Out)', 'State 4 (Evap In)', ''],
            textposition='top right',
            line=dict(color='black', width=3, dash='solid'),
            marker=dict(size=8, color='black')
        ))

        # Chart Configuration
        fig.update_layout(
            title=f"Pressure-Enthalpy (P-h) Diagram for {refrigerant}",
            xaxis_title="Enthalpy h (kJ/kg)",
            yaxis_title="Pressure P (bar, Log Scale)",
            yaxis_type="log",
            height=650,
            hovermode="closest",
            legend=dict(x=0.02, y=0.98)
        )

        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.subheader(f"Sensitivity: Heating COP vs {sens_var}")
    
        # Generate range based on selection
        if sens_var == "Evaporating Temperature":
            x_vals = np.linspace(-30, 15, 30)
            cops = [get_cycle_points(refrigerant, x, t_cond_c, superheat_k, subcooling_k, eta_is)['q_cond_kj'] /
                    get_cycle_points(refrigerant, x, t_cond_c, superheat_k, subcooling_k, eta_is)['w_comp_kj'] 
                    for x in x_vals if x < t_cond_c]
            x_label = "Evaporating Temperature (°C)"

        elif sens_var == "Condensing Temperature":
            x_vals = np.linspace(30, 70, 30)
            cops = [get_cycle_points(refrigerant, t_evap_c, x, superheat_k, subcooling_k, eta_is)['q_cond_kj'] /
                    get_cycle_points(refrigerant, t_evap_c, x, superheat_k, subcooling_k, eta_is)['w_comp_kj'] 
                    for x in x_vals if x > t_evap_c]
            x_label = "Condensing Temperature (°C)"

        elif sens_var == "Compressor Efficiency":
            x_vals = np.linspace(0.5, 0.95, 20)
            cops = [get_cycle_points(refrigerant, t_evap_c, t_cond_c, superheat_k, subcooling_k, x)['q_cond_kj'] /
                    get_cycle_points(refrigerant, t_evap_c, t_cond_c, superheat_k, subcooling_k, x)['w_comp_kj'] 
                    for x in x_vals]
            x_label = "Isentropic Efficiency"

        else:  # Superheating
            x_vals = np.linspace(0, 20, 20)
            cops = [get_cycle_points(refrigerant, t_evap_c, t_cond_c, x, subcooling_k, eta_is)['q_cond_kj'] /
                    get_cycle_points(refrigerant, t_evap_c, t_cond_c, x, subcooling_k, eta_is)['w_comp_kj'] 
                    for x in x_vals]
            x_label = "Superheating (K)"

        # Plot Sensitivity Line Chart
        sens_df = pd.DataFrame({x_label: x_vals[:len(cops)], "Heating COP": cops})
    
        sens_fig = go.Figure()
        sens_fig.add_trace(go.Scatter(
            x=sens_df[x_label], y=sens_df["Heating COP"],
            mode='lines+markers', line=dict(color='firebrick', width=3)
        ))
        sens_fig.update_layout(
            title=f"Impact of {sens_var} on Coefficient of Performance (COP)",
            xaxis_title=x_label,
            yaxis_title="COP (Heating)",
            height=500
        )
    
        st.plotly_chart(sens_fig, use_container_width=True)

elif app_mode == "Coaxial BHE (Coming Soon)":
    st.header("📐 Coaxial Borehole Exchanger Analysis")
    st.info("This feature will allow users to design coaxial bhe's and analyse heat output")

elif app_mode == "System Monitor (Coming Soon)":
    st.header("📊 Real-Time System Monitoring")
    st.info("This feature will integrate sensor data, indoor/outdoor temperatures, and real-time COP tracking.")
