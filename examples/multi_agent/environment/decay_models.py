# FLOODABM calibrated parameters and defaults for TP decay.
TAU_0 = 2.0       # tau_0: Initial half-life (years) - memory decays faster initially
TAU_INF = 8.0     # tau_inf: Asymptotic half-life (years) - long-term memory persistence
K_DECAY = 0.3     # k: Decay rate constant for half-life evolution

# TP Gain Parameters
THETA = 0.5       # theta: Damage ratio threshold for TP gain (50% damage)
SHOCK_SCALE = 0.3  # cs: Shock scaling factor (not used in current formula)

# Weighted decay coefficients
ALPHA = 0.4       # PA weight in decay formula
BETA = 0.6        # SC weight in decay formula

# MG-specific calibrated parameters (Table S4)
MG_PARAMS = {
    "alpha": 0.50,
    "beta": 0.21,
    "tau_0": 1.00,
    "tau_inf": 32.19,
    "k": 0.03,
}

# NMG-specific calibrated parameters (Table S4)
NMG_PARAMS = {
    "alpha": 0.22,
    "beta": 0.10,
    "tau_0": 2.72,
    "tau_inf": 50.10,
    "k": 0.01,
}
