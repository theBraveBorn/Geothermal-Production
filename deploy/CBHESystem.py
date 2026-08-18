import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.integrate import quad, cumulative_trapezoid
from scipy.special import erfc
from scipy.interpolate import CubicSpline

# CBHE simulation based on https://doi.org/10.1016/j.energy.2019.05.228
# with inclined modification
# ==============================================================================

class CoaxialBHE:
    def __init__(self, params, mode='vertical'):
        self.params = params
        self.mode = mode.lower()
        if self.mode not in ['vertical', 'inclined']:
            raise ValueError("Mode must be either 'vertical' or 'inclined'")
            
        if self.mode == 'vertical':
            self.alpha = 0.0
        else:
            self.alpha = np.radians(self.params.get('alpha', 0.0))
            
        self.delta = self.params.get('delta', 0)  # 0: Center flow down, 1: Annulus flow down
        self.initialize_model()

    def initialize_model(self):
        """Initialize model parameters according to mathematical formulation"""
        self.w = self.params['w']    # m³/s
        self.cw = self.params['cw']  # J/m³K
        self.H = self.params['H']    # Axial length (m)

        self.R_12 = self.params['R_12']
        self.R_b = self.params['R_b']
        self.N = self.params['N']

        # Dimensionless parameters
        self.N12 = self.H / (self.w * self.cw * self.R_12)
        self.Ns1 = self.H * self.delta / (self.w * self.cw * self.R_b)
        self.Ns2 = self.H * (1 - self.delta) / (self.w * self.cw * self.R_b)

        # Coefficients for analytical solution
        self.a1 = self.Ns1 - self.Ns2
        self.a2 = -(self.N12 * self.Ns1 + self.N12 * self.Ns2 + self.Ns1 * self.Ns2)
        
        discriminant = self.a1**2 - 4 * self.a2
        if abs(discriminant) < 1e-12:
            discriminant = 1e-12
            
        self.b1 = 0.5 * (-self.a1 - np.sqrt(discriminant))
        self.b2 = 0.5 * (-self.a1 + np.sqrt(discriminant))

    def calculate_equivalent_temperatures(self, T_gb_func):
        """Calculate equivalent profiles using precise dimensionless scales"""
        z_physical = np.linspace(0, self.H, self.N)
        z_eq_array = z_physical / self.H
        
        # 1. Dynamically calculate derivative of soil temperature
        if isinstance(T_gb_func, CubicSpline):
            dT_gb_dz_func = T_gb_func.derivative()
        else:
            dT_gb_dz_func = lambda z: self.params['grad_T'] * np.cos(self.alpha)
            
        T_eqb_array = (T_gb_func(z_physical) - self.params['T_rs']) / (self.params['T_in'] - self.params['T_rs'])
        dT_eqb_dzeq_array = (dT_gb_dz_func(z_physical) * self.H) / (self.params['T_in'] - self.params['T_rs'])
        
        # 2. Vectorized F(Z_eq) representing curved soil boundary
        F_array = self.Ns1 * dT_eqb_dzeq_array + self.a2 * T_eqb_array
        
        # 3. Vectorized integration using cumulative_trapezoid
        integrand1 = np.exp((self.a1 + self.b2) * z_eq_array) * F_array / (self.b1 - self.b2)
        integrand2 = np.exp((self.a1 + self.b1) * z_eq_array) * F_array / (self.b2 - self.b1)
        
        int1_0_z = cumulative_trapezoid(integrand1, z_eq_array, initial=0)
        int2_0_z = cumulative_trapezoid(integrand2, z_eq_array, initial=0)
        
        h1_array = int1_0_z - int1_0_z[-1]  # Forces h1(1) = 0 exactly
        h2_array = int2_0_z - int2_0_z[-1]  # Forces h2(1) = 0 exactly
        
        h1_0, h1_1 = h1_array[0], h1_array[-1]
        h2_0, h2_1 = h2_array[0], h2_array[-1]
        T_eqb_1 = T_eqb_array[-1]
    
        # 4. Calculate proper integration constants
        numerator = (
            (self.b1 + self.Ns1) * np.exp(self.b1) * h1_1 +
            (self.b2 + self.Ns1) * np.exp(self.b2) * (1.0 - h1_0 - h2_0 + h2_1) -
            self.Ns1 * T_eqb_1
        )
        denominator = -(self.b1 + self.Ns1) * np.exp(self.b1) + (self.b2 + self.Ns1) * np.exp(self.b2)
        
        c1 = numerator / denominator
        c2 = 1.0 - h1_0 - h2_0 - c1
    
        # 5. Reconstruct Dimensionless Temperatures
        T_eq1 = np.exp(self.b1 * z_eq_array) * (c1 + h1_array) + np.exp(self.b2 * z_eq_array) * (c2 + h2_array)
        
        term1 = np.exp(self.b1 * z_eq_array) * (c1 + h1_array) * (self.b1 + self.N12 + self.Ns1) / self.N12
        term2 = np.exp(self.b2 * z_eq_array) * (c2 + h2_array) * (self.b2 + self.N12 + self.Ns1) / self.N12
        term3 = (self.Ns1 / self.N12) * T_eqb_array
        
        T_eq2 = term1 + term2 - term3
    
        return z_physical, T_eq1, T_eq2

    def calculate_fluid_temperatures(self, T_eq1, T_eq2):
        """Convert dimensionless equivalent temperatures back to °C"""
        z = np.linspace(0, self.H, len(T_eq1))
        
        # Pipe 1 (center pipe) & Pipe 2 (annulus)
        T_f1 = self.params['T_rs'] + (self.params['T_in'] - self.params['T_rs']) * T_eq1
        T_f2 = self.params['T_rs'] + (self.params['T_in'] - self.params['T_rs']) * T_eq2
        
        return z, T_f1, T_f2


class SoilModel:
    def __init__(self, params, mode='vertical'):
        self.params = params
        self.N = params['N']
        self.dz = params['H'] / self.N
        self.z_segments = np.linspace(self.dz/2, params['H'] - self.dz/2, self.N)
        
        self.mode = mode.lower()
        if self.mode == 'vertical':
            self.alpha = 0.0
            self.beta = 0.0
        else:
            self.alpha = np.radians(self.params.get('alpha', 0.0))
            self.beta = np.radians(self.params.get('beta', 0.0))
            
        self.x0 = self.params.get('x0', 0.0)
        self.y0 = self.params.get('y0', 0.0)
        self.response_cache = {}

    def calculate_theta_2_constant(self, z_array, t):
        """Exact, steady-state geothermal gradient profile"""
        return self.params['T_surface'] + self.params['grad_T'] * z_array * np.cos(self.alpha)

    def calculate_unit_response(self, z_eval, z_i, z_ip1, t):
        """Thermal response at z_eval to a 1 W/m pulse between z_i and z_ip1"""
        if t <= 0: return 0.0
        
        cache_key = (round(z_eval, 4), round(z_i, 4), round(z_ip1, 4), round(t, 2))
        if cache_key in self.response_cache:
            return self.response_cache[cache_key]
            
        dx_offset = -self.params['rg'] * np.sin(self.beta)
        dy_offset = self.params['rg'] * np.cos(self.beta)
        
        x_p = self.x0 + z_eval * np.sin(self.alpha) * np.cos(self.beta) + dx_offset
        y_p = self.y0 + z_eval * np.sin(self.alpha) * np.sin(self.beta) + dy_offset
        z_p = z_eval * np.cos(self.alpha)

        def integrand(h):
            x_s_real = self.x0 + h * np.sin(self.alpha) * np.cos(self.beta)
            y_s_real = self.y0 + h * np.sin(self.alpha) * np.sin(self.beta)
            z_s_real = h * np.cos(self.alpha)
            
            x_s_virt = self.x0 + h * np.sin(self.alpha) * np.cos(self.beta)
            y_s_virt = self.y0 + h * np.sin(self.alpha) * np.sin(self.beta)
            z_s_virt = -h * np.cos(self.alpha)
            
            r_plus = max(np.sqrt((x_p - x_s_real)**2 + (y_p - y_s_real)**2 + (z_p - z_s_real)**2), 1e-10)
            r_minus = max(np.sqrt((x_p - x_s_virt)**2 + (y_p - y_s_virt)**2 + (z_p - z_s_virt)**2), 1e-10)
            
            term1 = erfc(r_plus / (2 * np.sqrt(self.params['alpha_s'] * t))) / r_plus
            term2 = erfc(r_minus / (2 * np.sqrt(self.params['alpha_s'] * t))) / r_minus
            return term1 - term2

        integral, _ = quad(integrand, z_i, z_ip1)
        ans = (1 / (4 * np.pi * self.params['k_s'])) * integral
        
        self.response_cache[cache_key] = ans
        return ans


class CBHESystem:
    def __init__(self, params, mode='vertical'):
        self.params = params
        self.mode = mode.lower()
        
        self.alpha = 0.0 if self.mode == 'vertical' else np.radians(self.params.get('alpha', 0.0))
            
        self.fluid_model = CoaxialBHE(params, mode=self.mode) 
        self.soil_model = SoilModel(params, mode=self.mode)
        
        self.time_history = []
        self.q_history = [] 
        
        self.N = params['N']
        dz = params['H'] / self.N
        self.z_nodes = np.linspace(dz/2, params['H'] - dz/2, self.N)
        self.T_b_current = params['T_surface'] + params['grad_T'] * self.z_nodes * np.cos(self.alpha)

    def execute_time_step(self, dt_seconds, current_time):
        """Executes a single transient solver iteration"""
        z_ext = np.zeros(self.N + 2)
        z_ext[1:-1] = self.z_nodes
        z_ext[0] = 0.0
        z_ext[-1] = self.params['H']
        
        T_ext = np.zeros(self.N + 2)
        T_ext[1:-1] = self.T_b_current
        
        T_ext[0] = self.T_b_current[0] - self.params['grad_T'] * (self.z_nodes[0] - 0) * np.cos(self.alpha)
        T_ext[-1] = self.T_b_current[-1] + self.params['grad_T'] * (self.params['H'] - self.z_nodes[-1]) * np.cos(self.alpha)

        def T_gb_func(z):
            f = CubicSpline(z_ext, T_ext)
            return f(z)
            
        z_fluid, T_eq1, T_eq2 = self.fluid_model.calculate_equivalent_temperatures(T_gb_func)
        _, T_f1, T_f2 = self.fluid_model.calculate_fluid_temperatures(T_eq1, T_eq2)
        
        T_annulus_fluid = T_f1 if self.fluid_model.delta == 1 else T_f2 
        T_annulus_segmented = np.interp(self.z_nodes, z_fluid, T_annulus_fluid)
        
        q_current = (T_annulus_segmented - self.T_b_current) / (self.params['R_b'] + self.params['R_12'])
        
        self.time_history.append(current_time)
        self.q_history.append(q_current)
        
        T_b_new = np.zeros(self.N)
        
        for i, z_eval in enumerate(self.z_nodes):
            theta_1_total = 0.0
            for j in range(self.N):
                z_j = j * (self.params['H'] / self.N)
                z_jp1 = (j + 1) * (self.params['H'] / self.N)
                
                for k in range(len(self.time_history)):
                    t_n = current_time
                    t_k_minus_1 = self.time_history[k-1] if k > 0 else 0
                    delta_q = self.q_history[k][j] - (self.q_history[k-1][j] if k > 0 else 0)
                    
                    response = self.soil_model.calculate_unit_response(z_eval, z_j, z_jp1, t_n - t_k_minus_1)
                    theta_1_total += delta_q * response
            
            theta_2_val = self.soil_model.calculate_theta_2_constant(z_eval, current_time)
            T_b_new[i] = theta_1_total + theta_2_val

        self.T_b_current = T_b_new
        
        # Outlet temperature determination based on flow direction
        T_out = T_f1[-1] if self.fluid_model.delta == 1 else T_f2[0]
        
        return T_out, T_b_new, z_fluid, T_f1, T_f2