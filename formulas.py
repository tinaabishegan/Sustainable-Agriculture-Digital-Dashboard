def calc_np_conv(unit, unit_weight, unit_class):
    N_perc, P205_perc, K_perc = unit_class.split("-")
    total_mass = unit * unit_weight
    N_perc = float(N_perc)/100
    P205_perc = float(P205_perc)/100
    P_perc = (P205_perc*62)/142
    N_applied = N_perc * total_mass
    P_applied = P_perc * total_mass
    return N_applied, P_applied

def calc_np_regen(unit, unit_weight):
    N_perc = 0.05
    P_perc = 0.005
    total_mass = unit * unit_weight
    N_applied = N_perc * total_mass
    P_applied = P_perc * total_mass
    return N_applied, P_applied

chemical_data = [
    {
        "name": "DEEBAJ",
        "units": 2,
        "unit_weight": 25,
        "unit_class": "15-15-15"
    },
    {
        "name": "Agroharta",
        "units": 1,
        "unit_weight": 2,
        "unit_class": "15-15-15"
    },
    {
        "name": "GuangFong",
        "units": 5,
        "unit_weight": 25,
        "unit_class": "5-5-5"
    },
    {
        "name": "Foliar",
        "units": 1,
        "unit_weight": 1.5,
        "unit_class": "10-5-12"
    }
]

# print(chemical_data)

def calc_ep_conv(chemical_data):
    N_applied, P_applied = 0, 0
    for chem in chemical_data:
        N, P = calc_np_conv(chem["units"], chem["unit_weight"], chem["unit_class"])
        print(N,P)
        N_applied += N
        P_applied += P
    N_used = N_applied * 12
    P_used = P_applied * 12
    EF_N = 1.33
    EF_P = 0.05
    emission_N = N_used * EF_N
    emission_P = P_used * EF_P
    midpoint_CF_N = 0.158
    midpoint_CF_P = 0.100
    EP_P = emission_P * midpoint_CF_P
    EP_N = emission_N * midpoint_CF_N
    CEF_N = 3.7
    CEF_P = 3.1
    C_FP_N = CEF_N * N_used
    C_FP_P = CEF_P * P_used
    CFP = C_FP_P + C_FP_N
    return EP_N, EP_P, CFP

def calc_ep_regen(chemical_data):
    N_applied, P_applied = calc_np_regen(chemical_data[0]["units"], chemical_data[0]["unit_weight"])
    N_used = N_applied * 12
    P_used = P_applied * 12
    EF_N = 1.33
    EF_P = 0.05
    emission_N = N_used * EF_N
    emission_P = P_used * EF_P
    midpoint_CF_N = 0.158
    midpoint_CF_P = 0.100
    EP_P = emission_P * midpoint_CF_P
    EP_N = emission_N * midpoint_CF_N
    C_uptake = -1.83
    CFP = chemical_data[0]["units"] * chemical_data[0]["unit_weight"] * C_uptake * 12
    return EP_N, EP_P, CFP

default_conv_chemicals = [
                    {"name": "DEEBAJ", "units": 2, "unit_weight": 25, "unit_class": "15-15-15"},
                    {"name": "Agroharta", "units": 1, "unit_weight": 2, "unit_class": "15-15-15"},
                    {"name": "GuangFong", "units": 5, "unit_weight": 25, "unit_class": "5-5-5"},
                    {"name": "Foliar", "units": 1, "unit_weight": 1.5, "unit_class": "10-5-12"}
                ]

print(calc_ep_conv(default_conv_chemicals))


# # --- Soil Health Metrics ---
# st.subheader("Soil Health Improvement")

# with card(title="Comparison of Soil Metrics", key="soil_health_charts_card"):
#     try:
#         # Prepare data for plotting
#         soil_health_comparison_df = soil_health_df.reset_index()
#         soil_health_comparison_df = soil_health_comparison_df.rename(columns={soil_health_comparison_df.columns[0]: 'Farming Method'})
        
#         # A function to create a compact horizontal bar chart for a given metric
#         def create_soil_metric_chart(df, metric_col, title):
#             fig = px.bar(
#                 df,
#                 x=metric_col,
#                 y='Farming Method',
#                 orientation='h',
#                 title=title,
#                 color='Farming Method',
#                 color_discrete_map={
#                     'Before Regenerative Farming': '#D2B48C', # Tan Brown
#                     'After Regenerative Farming 2 months': '#228B22' # Forest Green
#                 },
#                 text_auto='.2f'
#             )
#             fig.update_layout(
#                 showlegend=False,
#                 height=180, # Compact height
#                 margin=dict(l=10, r=10, t=40, b=20),
#                 yaxis_title=None,
#                 xaxis_title=None,
#                 font=dict(size=10) # Smaller font for a compact look
#             )
#             fig.update_traces(textposition='outside')
#             st.plotly_chart(fig, use_container_width=True)

#         # Create and display a chart for each soil health metric
#         create_soil_metric_chart(soil_health_comparison_df, 'Organic Matter (%)', 'Organic Matter (%)')
#         create_soil_metric_chart(soil_health_comparison_df, 'Total Carbon (%)', 'Total Carbon (%)')
#         create_soil_metric_chart(soil_health_comparison_df, 'Total Nitrogen (%)', 'Total Nitrogen (%)')

#     except (KeyError, Exception) as e:
#         st.warning(f"Could not create soil health comparison charts. Please check the 'SoilHealth' sheet. Error: {e}")
