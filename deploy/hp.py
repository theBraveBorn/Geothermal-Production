import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from CBHESystem import CBHESystem

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
    ["Heat Pump Analysis", "Coaxial BHE", "System Monitor (Coming Soon)"]
)
if app_mode == "Heat Pump Analysis":
    refrigerant = st.sidebar.selectbox(
        "Select Refrigerant",
        ["R744","R134a", "R410A", "R32", "R290", "R1234yf", "R717"],
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


# CBHE Implementation

elif app_mode == "Coaxial BHE":
    st.title("♨️ Coaxial Borehole Heat Exchanger (CBHE) Engine")
    st.markdown(
        "Design, cost, and dynamically simulate coaxial geothermal deep borehole heat exchangers "
        "using rigorous semi-analytical thermal models and transient line-source superposition."
    )

    tab1, tab2 = st.tabs([
        "📐 Coaxial BHE Design & Costing", 
        "⚡ Dynamic Thermal Simulation & Flow Visualizer"
    ])

    # --------------------------------------------------------------------------
    # TAB 1: DESIGN & COSTING
    # --------------------------------------------------------------------------
    with tab1:
        st.subheader("Borehole & Pipe Geometry Design")
        
        col1, col2, col3 = st.columns([1, 1, 1])

        with col1:
            st.markdown("##### 📏 Borehole Trajectory")
            H_val = st.slider("Borehole Axial Length H (m)", 20.0, 500.0, 100.0, step=10.0)
            D_b_mm = st.number_input("Borehole Diameter Db (mm)", min_value=80.0, max_value=400.0, value=150.0, step=5.0)
            rg_val = (D_b_mm / 1000.0) / 2.0  # m

            alpha_deg = st.slider("Inclination Angle α (deg)", 0.0, 75.0, 0.0, step=5.0)
            beta_deg = st.slider("Azimuth Angle β (deg)", 0.0, 360.0, 45.0, step=15.0)
            mode_choice = "vertical" if alpha_deg == 0.0 else "inclined"

        with col2:
            st.markdown("##### ⭕ Pipe Dimensions (Radii in mm)")
            r1i_mm = st.number_input("Inner Pipe Inner Radius r1i (mm)", 10.0, 80.0, 20.0, step=1.0)
            r1o_mm = st.number_input("Inner Pipe Outer Radius r1o (mm)", 12.0, 90.0, 25.0, step=1.0)
            r2i_mm = st.number_input("Outer Pipe Inner Radius r2i (mm)", 20.0, 150.0, 55.0, step=1.0)
            r2o_mm = st.number_input("Outer Pipe Outer Radius r2o (mm)", 25.0, 180.0, 63.0, step=1.0)

        with col3:
            st.markdown("##### 🏗️ Materials & Resistances")
            inner_mat = st.selectbox(
                "Inner Pipe Material", 
                ["Vacuum Insulated Pipe (VIP)", "HDPE (High Density Polyethylene)", "PEX", "Stainless Steel"]
            )
            outer_mat = st.selectbox("Outer Pipe Material", ["Steel Casing", "HDPE Standard", "Composite Fiber"])
            grout_mat = st.selectbox("Grout Type", ["Thermally Enhanced Grout (2.0 W/mK)", "Standard Bentonite (0.8 W/mK)", "Graphite Additive Grout (3.0 W/mK)"])

            # Map materials to default resistances
            R12_default = 0.25 if "VIP" in inner_mat else (0.08 if "HDPE" in inner_mat else 0.02)
            Rb_default = 0.08 if "Enhanced" in grout_mat else (0.134 if "Standard" in grout_mat else 0.05)

            R_12_val = st.number_input("Internal Thermal Resistance R12 (m·K/W)", 0.001, 1.0, R12_default, step=0.01)
            R_b_val = st.number_input("Borehole Thermal Resistance Rb (m·K/W)", 0.001, 1.0, Rb_default, step=0.01)

        # Geometric Integrity Validation
        r1i, r1o = r1i_mm / 1000.0, r1o_mm / 1000.0
        r2i, r2o = r2i_mm / 1000.0, r2o_mm / 1000.0

        geom_valid = True
        err_msg = ""

        if r1i >= r1o:
            geom_valid = False
            err_msg = "Inner pipe inner radius (r1i) must be smaller than inner pipe outer radius (r1o)."
        elif r1o >= r2i:
            geom_valid = False
            err_msg = "Inner pipe outer radius (r1o) must be smaller than outer pipe inner radius (r2i)."
        elif r2i >= r2o:
            geom_valid = False
            err_msg = "Outer pipe inner radius (r2i) must be smaller than outer pipe outer radius (r2o)."
        elif r2o >= rg_val:
            geom_valid = False
            err_msg = f"Outer pipe outer radius (r2o = {r2o_mm}mm) must be smaller than Borehole radius (rg = {rg_val*1000}mm)."

        if not geom_valid:
            st.error(f"❌ Geometry Constraint Error: {err_msg}")
            st.stop()
        else:
            st.success("✅ Geometry validation passed! Concentric clearance verified.")

        st.markdown("---")

        # ----------------------------------------------------------------------
        # CAPEX COST CALCULATOR
        # ----------------------------------------------------------------------
        st.subheader("💰 Itemized CAPEX Estimator")
        
        with st.expander("⚙️ Modify Unit Cost Rates", expanded=False):
            cost_col1, cost_col2, cost_col3, cost_col4 = st.columns(4)
            c_drill = cost_col1.number_input("Drilling ($/m)", 20.0, 500.0, 80.0, step=5.0)
            c_inner = cost_col2.number_input("Inner Pipe ($/m)", 5.0, 300.0, 45.0 if "VIP" in inner_mat else 15.0)
            c_outer = cost_col3.number_input("Outer Pipe ($/m)", 10.0, 400.0, 35.0)
            c_grout = cost_col4.number_input("Grout ($/m)", 5.0, 100.0, 20.0)
            c_mob = st.number_input("Mobilization & Installation Fixed Cost ($)", 0.0, 50000.0, 5000.0, step=500.0)

        cost_drilling = H_val * c_drill
        cost_inner_pipe = H_val * c_inner
        cost_outer_pipe = H_val * c_outer
        cost_grout = H_val * c_grout
        cost_total = cost_drilling + cost_inner_pipe + cost_outer_pipe + cost_grout + c_mob
        cost_per_m = cost_total / H_val

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Vertical Depth", f"{H_val * np.cos(np.radians(alpha_deg)):.1f} m", f"Axial: {H_val:.0f} m")
        m2.metric("Inner / Outer Annulus Ratio", f"{(r1o_mm / r2i_mm):.2f}", f"Clearance: {(r2i_mm - r1o_mm):.1f} mm")
        m3.metric("Total CAPEX", f"${cost_total:,.2f}")
        m4.metric("Unit Cost per Meter", f"${cost_per_m:.2f} / m")

        # Visualizations: Donut Chart & Schematics
        vcol1, vcol2 = st.columns([1, 1.2])

        with vcol1:
            st.markdown("##### 📊 CAPEX Cost Breakdown")
            cost_labels = ["Drilling", "Inner Pipe", "Outer Pipe", "Grout Material", "Mob/Installation"]
            cost_values = [cost_drilling, cost_inner_pipe, cost_outer_pipe, cost_grout, c_mob]
            
            fig_donut = go.Figure(data=[go.Pie(
                labels=cost_labels, 
                values=cost_values, 
                hole=0.45,
                marker=dict(colors=["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"])
            )])
            fig_donut.update_layout(
                margin=dict(l=10, r=10, t=30, b=10),
                height=320,
                legend=dict(orientation="h", y=-0.1)
            )
            st.plotly_chart(fig_donut, use_container_width=True)

        with vcol2:
            st.markdown("##### 🎯 Concentric Cross-Sectional Schematic")
            fig_cross = go.Figure()

            # Circles representing layers
            radii = [r1i_mm, r1o_mm, r2i_mm, r2o_mm, rg_val * 1000.0]
            names = ["Inner Fluid Core", "Inner Pipe Wall", "Annulus Fluid", "Outer Pipe Wall", "Grout Layer"]
            colors = ["#70d6ff", "#ff70a6", "#ff9770", "#ffd670", "#e9d8a6"]

            theta = np.linspace(0, 2*np.pi, 100)

            # Draw outer ground boundary background
            r_ground = rg_val * 1000.0 * 1.3
            fig_cross.add_trace(go.Scatter(
                x=r_ground * np.cos(theta), y=r_ground * np.sin(theta),
                fill="toself", fillcolor="#d8f3dc", line=dict(color="#2dc653", width=1),
                name="Surrounding Rock/Ground", hoverinfo="name"
            ))

            for r, name, col in zip(reversed(radii), reversed(names), reversed(colors)):
                fig_cross.add_trace(go.Scatter(
                    x=r * np.cos(theta), y=r * np.sin(theta),
                    fill="toself", fillcolor=col, line=dict(color="#333333", width=1.5),
                    name=f"{name} ({r:.1f} mm)", hoverinfo="name+text", text=[f"Radius: {r:.1f} mm"]*100
                ))

            fig_cross.update_layout(
                xaxis=dict(visible=False, scaleanchor="y", scaleratio=1),
                yaxis=dict(visible=False),
                margin=dict(l=10, r=10, t=10, b=10),
                height=320,
                showlegend=True,
                legend=dict(font=dict(size=10))
            )
            st.plotly_chart(fig_cross, use_container_width=True)

    # --------------------------------------------------------------------------
    # TAB 2: DYNAMIC THERMAL SIMULATION
    # --------------------------------------------------------------------------
    with tab2:
        st.subheader("⚙️ Operational & Ground Parameters")

        pcol1, pcol2, pcol3 = st.columns(3)

        with pcol1:
            st.markdown("##### ⏱️ Temporal Setup")
            sim_hours = st.slider("Simulation Duration (Hours)", 1, 48, 6, step=1)
            dt_mins = st.selectbox("Time Step dt", [10, 15, 30, 60], index=3)
            N_nodes = st.slider("Discretization Nodes N", 10, 100, 30, step=10)

        with pcol2:
            st.markdown("##### 💧 Hydraulic Parameters")
            flow_lmin = st.number_input("Fluid Flow Rate (L/min)", 5.0, 200.0, 30.0, step=5.0)
            w_m3s = (flow_lmin / 1000.0) / 60.0  # m³/s
            cw_val = 4.19e6  # J/m³K (Water)

            flow_mode = st.radio(
                "Flow Direction Mode", 
                ["Direct Coaxial (Down Center, Up Annulus)", "Reverse Coaxial (Down Annulus, Up Center)"]
            )
            delta_val = 0 if "Direct" in flow_mode else 1

        with pcol3:
            st.markdown("##### 🌡️ Thermal Environment")
            T_in_val = st.number_input("Inlet Temperature Tin (°C)", -5.0, 40.0, 10.0, step=1.0)
            T_surf_val = st.number_input("Surface Temperature Tsurf (°C)", -10.0, 30.0, 12.0, step=1.0)
            grad_T_val = st.number_input("Geothermal Gradient (°C/m)", 0.01, 0.10, 0.035, step=0.005)
            k_s_val = st.number_input("Soil Thermal Conductivity ks (W/m·K)", 1.0, 5.0, 2.8, step=0.1)

        st.markdown("---")

        # Session State Initialization for Transient Results
        if "sim_run_completed" not in st.session_state:
            st.session_state.sim_run_completed = False

        if st.button("▶️ Run Transient Simulation", type="primary", use_container_width=True):
            dt_sec = dt_mins * 60
            total_steps = int((sim_hours * 3600) / dt_sec)

            # Construct parameter dictionary directly from UI
            sim_params = {
                'H': H_val,
                'N': N_nodes,
                'alpha': alpha_deg,
                'beta': beta_deg,
                'x0': 0.0,
                'y0': 0.0,
                'rg': rg_val,
                'w': w_m3s,
                'cw': cw_val,
                'T_in': T_in_val,
                'T_rs': T_surf_val,
                'T_surface': T_surf_val,
                'T_infinity': T_surf_val + grad_T_val * 2 * (H_val * np.cos(np.radians(alpha_deg))),
                'grad_T': grad_T_val,
                'R_12': R_12_val,
                'R_b': R_b_val,
                'R_s': 0.01,
                'alpha_s': 1.406e-6,
                'k_s': k_s_val,
                'delta': delta_val
            }

            system = CBHESystem(sim_params, mode=mode_choice)
            
            progress_bar = st.progress(0.0)
            status_text = st.empty()

            history_time = []
            history_Tout = []
            history_Q = []
            history_Tb_avg = []
            profile_snapshots = []

            for step in range(1, total_steps + 1):
                current_time_sec = step * dt_sec
                current_hr = current_time_sec / 3600.0

                T_out, T_b_prof, z_fl, Tf1, Tf2 = system.execute_time_step(dt_sec, current_time_sec)
                
                # Calculate Heat Extraction Rate (kW)
                # Q = w * cw * (Tout - Tin) / 1000
                Q_kW = (w_m3s * cw_val * (T_out - T_in_val)) / 1000.0

                history_time.append(current_hr)
                history_Tout.append(T_out)
                history_Q.append(Q_kW)
                history_Tb_avg.append(np.mean(T_b_prof))

                profile_snapshots.append({
                    'hour': current_hr,
                    'z': z_fl.copy(),
                    'Tf1': Tf1.copy(),
                    'Tf2': Tf2.copy(),
                    'Tb': T_b_prof.copy(),
                    'z_nodes': system.z_nodes.copy()
                })

                frac = step / total_steps
                progress_bar.progress(frac)
                status_text.text(f"Simulating Time Step {step}/{total_steps} (Hour {current_hr:.2f}) - Tout = {T_out:.2f} °C")

            status_text.success("🎉 Simulation Completed Successfully!")

            # Store in Session State
            st.session_state.sim_results = {
                'time': history_time,
                'Tout': history_Tout,
                'Q_kW': history_Q,
                'Tb_avg': history_Tb_avg,
                'snapshots': profile_snapshots,
                'params': sim_params
            }
            st.session_state.sim_run_completed = True

        # Render Simulation Results
        if st.session_state.sim_run_completed:
            res = st.session_state.sim_results
            
            st.markdown("### 📈 Transient Performance KPIs")
            kpi1, kpi2, kpi3, kpi4 = st.columns(4)

            last_Tout = res['Tout'][-1]
            last_Q = res['Q_kW'][-1]
            cum_energy_kWh = np.trapezoid(res['Q_kW'], res['time'])
            last_Tb = res['Tb_avg'][-1]

            kpi1.metric("Final Outlet Temp (Tout)", f"{last_Tout:.2f} °C", f"{last_Tout - T_in_val:+.2f} °C ΔT")
            kpi2.metric("Heat Rate (Q)", f"{last_Q:.2f} kW", "Extraction" if last_Q > 0 else "Injection")
            kpi3.metric("Cumulative Energy", f"{cum_energy_kWh:.2f} kWh")
            kpi4.metric("Avg Borehole Wall Temp", f"{last_Tb:.2f} °C")

            st.markdown("---")

            # ------------------------------------------------------------------
            # VISUALIZER: ANIMATED / SLIDER PROFILES & TIME-SERIES
            # ------------------------------------------------------------------
            vtab1, vtab2 = st.columns([1.1, 0.9])

            with vtab1:
                st.markdown("##### 🌡️ Depth vs. Temperature Profiles")
                snapshots = res['snapshots']
                max_snap_idx = len(snapshots) - 1

                selected_idx = st.slider("Select Simulation Snapshot (Hour)", 0, max_snap_idx, max_snap_idx, format="Step %d")
                snap = snapshots[selected_idx]

                depth_scale = np.cos(np.radians(alpha_deg))
                z_vert = snap['z'] * depth_scale
                z_nodes_vert = snap['z_nodes'] * depth_scale

                fig_prof = go.Figure()

                # Determine Pipe Labels according to delta
                if delta_val == 0:
                    lbl_pipe1 = "Pipe 1 (Center Pipe, Downward ⬇️)"
                    lbl_pipe2 = "Pipe 2 (Annulus Space, Upward ⬆️)"
                else:
                    lbl_pipe1 = "Pipe 1 (Center Pipe, Upward ⬆️)"
                    lbl_pipe2 = "Pipe 2 (Annulus Space, Downward ⬇️)"

                # Fluid Profiles
                fig_prof.add_trace(go.Scatter(
                    x=snap['Tf1'], y=-z_vert, mode='lines',
                    name=lbl_pipe1, line=dict(color='red', width=3)
                ))
                fig_prof.add_trace(go.Scatter(
                    x=snap['Tf2'], y=-z_vert, mode='lines',
                    name=lbl_pipe2, line=dict(color='blue', width=3, dash='dash')
                ))

                # Borehole Wall Temperature Profile
                borehole_plot = False
                if borehole_plot:
                    fig_prof.add_trace(go.Scatter(
                        x=snap['Tb'], y=-z_nodes_vert, mode='lines+markers',
                        name="Borehole Wall (Tb)", line=dict(color='black', width=2)
                    ))

                fig_prof.update_layout(
                    title=f"Temperature Profiles at Hour {snap['hour']:.2f}",
                    xaxis=dict(title="Temperature (°C)", side='top'),
                    yaxis=dict(title="Vertical Depth (m)"),
                    height=450,
                    margin=dict(l=10, r=10, t=50, b=10),
                    legend=dict(orientation="h", y=-0.15)
                )
                st.plotly_chart(fig_prof, use_container_width=True)

            with vtab2:
                st.markdown("##### ⏳ Transient Performance History")
                
                fig_hist = make_subplots(specs=[[{"secondary_y": True}]])

                fig_hist.add_trace(
                    go.Scatter(x=res['time'], y=res['Tout'], name="Outlet Temp Tout (°C)", line=dict(color="crimson", width=2.5)),
                    secondary_y=False
                )
                fig_hist.add_trace(
                    go.Scatter(x=res['time'], y=res['Q_kW'], name="Heat Rate Q (kW)", line=dict(color="teal", width=2, dash='dot')),
                    secondary_y=True
                )

                fig_hist.update_xaxes(title_text="Time (Hours)")
                fig_hist.update_yaxes(title_text="Outlet Temp (°C)", secondary_y=False)
                fig_hist.update_yaxes(title_text="Heat Rate (kW)", secondary_y=True)

                fig_hist.update_layout(
                    title="Outlet Temperature & Heat Extraction Rate",
                    height=450,
                    margin=dict(l=10, r=10, t=50, b=10),
                    legend=dict(orientation="h", y=-0.2)
                )
                st.plotly_chart(fig_hist, use_container_width=True)

elif app_mode == "System Monitor (Coming Soon)":
    st.header("📊 Real-Time System Monitoring")
    st.info("This feature will integrate sensor data, indoor/outdoor temperatures, and real-time COP tracking.")
