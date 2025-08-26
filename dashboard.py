import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_shadcn_ui import card

from chatbot import get_rag_chain
import requests

# Assuming your new API server is running on localhost at port 5000
CHATBOT_API_URL = "http://127.0.0.1:5000/ask"
# =================================================================================
# 1. PAGE CONFIGURATION & STYLING
# =================================================================================

st.set_page_config(layout="wide", page_title="Regenerative Agriculture Dashboard")

# --- Inject Custom CSS for styling ---
st.markdown("""
<style>
    /* Using Google's Inter font */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    html, body, [class*="st-"], .st-emotion-cache-18ni7ap, .st-emotion-cache-z5fcl4 {
        font-family: 'Inter', sans-serif;
    }
    
    /* Main app background */
    .st-emotion-cache-z5fcl4 {
        background-color: #f7f7f7;
    }

    /* Remove Streamlit's default top margin */
    .st-emotion-cache-18ni7ap {
        padding-top: 0rem;
    }

    /* Custom card styling */
    .metric-card {
        background-color: #4a90e2;
        color: white;
        padding: 1.5rem;
        border-radius: 0.75rem;
        box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
        display: flex;
        flex-direction: column;
        justify-content: center; /* Vertically centers the content */
        height: 70%;
        text-align: center; /* Horizontally centers the text */
    }
    .metric-card h3 {
        font-size: 1.4rem;
        font-weight: 700; /* Bold label */
        margin-top: 0rem; /* Reduced space between number and label */
    }
    .metric-card p {
        font-size: 2.25rem;
        font-weight: 700; /* Bold number */
        margin: 0; /* Removes extra vertical margin */
    }
    
    /* Chart container styling */
    .chart-container {
        background-color: white;
        padding: 1.5rem;
        border-radius: 0.75rem;
        box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
    }
</style>
""", unsafe_allow_html=True)



# Set page configuration
st.set_page_config(layout="wide", page_title="Regenerative Agriculture Dashboard")

# Title of the dashboard
st.title("Digital Dashboard: Regenerative vs Conventional Agriculture")

# --- Calculation Functions ---

def calculate_sqi(som_value, cec_value, tc_value, tn_value):
    def get_score(metric_name, value):
        """Helper function to find the score for a single metric."""
        thresholds = {
            'SOM': {'very_low': 1, 'low': 2, 'average': 5},
            'CEC': {'very_low': 10, 'low': 15, 'average': 40},
            'TC': {'very_low': 3, 'low': 4, 'average': 9},
            'TN': {'very_low': 0.1, 'low': 0.3, 'average': 0.6}
        }
        metric_thresholds = thresholds[metric_name.upper()]
        
        if value < metric_thresholds['very_low']:
            return 1
        elif value <= metric_thresholds['low']:
            return 2
        elif value <= metric_thresholds['average']:
            return 3
        else:
            return 4

    som_score = get_score('SOM', som_value)
    cec_score = get_score('CEC', cec_value)
    tc_score = get_score('TC', tc_value)
    tn_score = get_score('TN', tn_value)

    total_score = som_score + cec_score + tc_score + tn_score
    sqi = total_score * 6.25

    category = ''
    if sqi <= 50:
        category = 'Poor'
    elif sqi <= 80:
        category = 'Average'
    else:
        category = 'Good'
    
    scores = {
        'SOM': som_score,
        'CEC': cec_score,
        'TC': tc_score,
        'TN': tn_score
    }

    return sqi, category, scores

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

def calc_ep_conv(chemical_data):
    N_applied, P_applied = 0, 0
    for chem in chemical_data:
        N, P = calc_np_conv(chem["units"], chem["unit_weight"], chem["unit_class"])
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


# --- Data Loading ---
# Load data from the specific sheets of the Excel file.
try:
    # Load cost data
    cost_df = pd.read_excel('PlotData.xlsx', sheet_name='Cost')
    
    # --- Robust Yield Data Loading ---
    # This method reads the specific columns for Grade A and Grade B harvest weights.

    # For Limau Nipis
    yield_nipis_df = pd.read_excel(
        'PlotData.xlsx',
        sheet_name='Yield',
        skiprows=2,  # Skip the title and header rows
        nrows=2,     # Read only the two data rows
        usecols="A,C:D", # Read the Farming Method, Grade A (kg), and Grade B (kg) columns
        header=None
    )
    yield_nipis_df.columns = [
        'Farming Method',
        'Grade A (kg)',
        'Grade B (kg)'
    ]
    
    # For Limau Kasturi
    yield_kasturi_df = pd.read_excel(
        'PlotData.xlsx',
        sheet_name='Yield',
        skiprows=7, # Skip all rows above the Kasturi data
        nrows=2,
        usecols="A,C:D",
        header=None
    )
    yield_kasturi_df.columns = [
        'Farming Method',
        'Grade A (kg)',
        'Grade B (kg)'
    ]

    # For Disaggregated Data
    disaggregation_df = pd.read_excel(
        'PlotData.xlsx',
        sheet_name='Yield',
        skiprows=13, # Updated skiprows to correctly target the data
        nrows=2,
        usecols="A:C",
        header=None,
        index_col=0
    )
    disaggregation_df.columns = [
        'Conventional Farming',
        'Regenerative Farming'
    ]

    # For Eutrophication Potential Data
    ep_df = pd.read_excel('PlotData.xlsx', sheet_name='EP', index_col=0)


    soil_health_df = pd.read_excel('PlotData.xlsx', sheet_name='SoilHealth', index_col=0)
    
    # For Plant Harvest Data
    plant_harvest_df = pd.read_excel('Plant Harvest.xlsx', sheet_name='Plant Harvest (Cleaned)', header=1)

except FileNotFoundError as e:
    st.error(f"Error loading data files. Please make sure '{e.filename}' is in the same directory.")
    st.stop()
except Exception as e:
    st.error(f"An error occurred while reading the Excel file: {e}")
    st.stop()


def render_sqi():
    """
    Renders the Soil Quality Index (SQI) section in a Streamlit app.
    The layout is improved for better alignment and visual appeal by ensuring elements do not overlap.
    """
    # --- Soil Quality Index ---
    st.markdown(f"""<div style="text-align: center;"><div style="font-weight: bold; font-size: 1.4em; margin-bottom: 40px;">Soil Quality Index (SQI)</div></div>""", unsafe_allow_html=True)

    try:
        sqi_score, sqi_category, scores = calculate_sqi(
            som_value=soil_health_df.loc['After Regenerative Farming 2 months', 'Organic Matter (%)'],
            cec_value=34.6475,  # Assumed CEC value
            tc_value=soil_health_df.loc['After Regenerative Farming 2 months', 'Total Carbon (%)'],
            tn_value=soil_health_df.loc['After Regenerative Farming 2 months', 'Total Nitrogen (%)']
        )

        def get_score_category_html(metric_name, score):
            """Returns HTML for a single metric's score and category."""
            categories = {1: "Poor 😞", 2: "Average 😐", 3: "Good 🙂", 4: "Excellent 😄"}
            return f'<div style="font-size: 1.1em; margin-bottom: 5px;"><b>{metric_name}:</b> {categories.get(score, "N/A")}</div>'
        
        # Find the metric with the lowest score for recommendation
        lowest_score_metric = min(scores, key=scores.get)
        
        # Define dynamic colours for SQI category
        sqi_color_map = {
            'Poor': '#FF4136', 
            'Average': '#FFDC00', 
            'Good': '#2ECC40'
        }
        sqi_color = sqi_color_map.get(sqi_category, '#A9A9A9')
        
        # --- Simplified Layout: Single row of two columns ---
        # A container to hold the gauge and scores side-by-side
        gap, gauge_col, gap3, scores_col, gap2 = st.columns([1, 2,0.5,2,1])

        with gauge_col:
            # Gauge-like visualisation
            st.markdown(f"""
            <div style="
                border: 10px solid {sqi_color};
                border-radius: 50%;
                width: 170px;
                height: 170px;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                background-color: #F0FFF0;
                box-shadow: 2px 2px 10px rgba(0,0,0,0.1);
            ">
                <span style="font-size: 2em; font-weight: bold; color: {sqi_color};">{sqi_score:.1f}</span>
                <span style="font-size: 1.2em; font-weight: bold; color: {sqi_color};">{sqi_category}</span>
            </div>
            """, unsafe_allow_html=True)
            
        with scores_col:
            # Breakdown of scores
            st.markdown(get_score_category_html("SOM", scores['SOM']), unsafe_allow_html=True)
            st.markdown(get_score_category_html("TC", scores['TC']), unsafe_allow_html=True)
            st.markdown(get_score_category_html("TN", scores['TN']), unsafe_allow_html=True)
            st.markdown(get_score_category_html("CEC", scores['CEC']), unsafe_allow_html=True)
        
        # The recommendation is a full-width element below the main content
        st.markdown(f"""
            <div style="text-align: center; margin-top: 45px; font-size: 1.1em;">
                Keep it up! Focus on improving the <b>{lowest_score_metric}</b> score.
            </div>
        """, unsafe_allow_html=True)
            
    except (KeyError, Exception) as e:
        st.warning(f"Could not calculate SQI. Error: {e}")

def render_cost_comparison():
    # --- Cost Comparison ---
    st.subheader("Monthly Cost Comparison")
    # Extract and process cost data for stacked bar chart
    try:
        # Address SettingWithCopyWarning by creating a new dataframe or using recommended assignment
        cost_processed_df = cost_df.copy()
        cost_processed_df = cost_processed_df.rename(columns={cost_processed_df.columns[0]: 'Farming Method'})
        cost_processed_df['Farming Method'] = cost_processed_df['Farming Method'].ffill()
        cost_chart_df = cost_processed_df[['Farming Method', 'Category', 'Cost (RM)']].dropna()

        color_map = {
            'Pesticide + Foliar Agrochemicals': "#003866",  # Steel Blue
            'Fertilizer': "#008F94",                  # Cadet Blue
            'Soil Regenerative Agent': "#005525",     # Sea Green
            'Pesticides': "#009E00"                   # Dark Sea Green
        }

        fig_cost = px.bar(
            cost_chart_df,
            x='Farming Method', 
            y='Cost (RM)',      
            color='Category',
            text_auto='.0f',
            labels={'Cost (RM)': 'Total Cost (RM)', 'Farming Method': ''},
            color_discrete_map=color_map
        )
        
        # --- UPDATED: Layout adjusted for cleaner look and legend position ---
        fig_cost.update_layout(
            title='Month Cost By Category',
            xaxis_title=None,
            yaxis_title='Total Cost (RM)',
            legend_title_text='Category', # Shortened title for clarity
            barmode='stack',
            plot_bgcolor='rgba(0,0,0,0)', # Set plot background to transparent
            
            # --- NEW: Makes bars thinner by increasing the gap between them ---
            bargap=0.5,

            # --- NEW: Hides background grid lines on both axes ---
            xaxis=dict(categoryorder='total descending', showgrid=False),
            yaxis=dict(showgrid=False),

            margin=dict(l=20, r=20, t=50, b=20),
            height=385,
            
            # --- NEW: Moves the legend to the right side of the chart ---
            legend=dict(
                orientation="v", # Vertical orientation
                yanchor="top",
                y=1,
                xanchor="left",
                x=1.02
            )
        )
        fig_cost.update_traces(textposition='inside')

        st.plotly_chart(fig_cost, use_container_width=True)

    except (KeyError, IndexError, Exception) as e:
        st.warning(f"Could not process cost data for the stacked chart. Error: {e}")
    
def render_ep_reduction():
    try:
        # Get EP values
        ep_n_conv = ep_df.loc['Eutrophication Potential N(kg N eq)', 'Conventional Farming']
        ep_n_regen = ep_df.loc['Eutrophication Potential N(kg N eq)', 'Regenerative Farming']
        ep_p_conv = ep_df.loc['Eutrophication Potential P(kg PO4 eq)', 'Conventional Farming']
        ep_p_regen = ep_df.loc['Eutrophication Potential P(kg PO4 eq)', 'Regenerative Farming']
        cf_conv = ep_df.loc['Carbon Footprint(kg CO2eq)', 'Conventional Farming']
        cf_regen = ep_df.loc['Carbon Footprint(kg CO2eq)', 'Regenerative Farming']

        # Calculate percentage reduction
        cf_reduction = ((cf_conv - cf_regen) / cf_conv) * 100
        n_reduction = ((ep_n_conv - ep_n_regen) / ep_n_conv) * 100
        p_reduction = ((ep_p_conv - ep_p_regen) / ep_p_conv) * 100
        
        def create_full_impact_viz(label, conv_val, regen_val, reduction_percent, unit):
            color = '#1E90FF' if reduction_percent > 0 else '#FF4136'
            html = f"""
            <div style="text-align: center;">
                <div style="font-weight: bold; font-size: 1.4em; margin-bottom: 10px;">{label}</div>
                <div style="
                    border: 8px solid {color};
                    border-radius: 50%; width: 160px; height: 160px;
                    display: flex; flex-direction: column; align-items: center; justify-content: center;
                    margin: 0 auto 10px auto;
                ">
                    <span style="font-size: 1.5em; font-weight: bold; color: {color};">{reduction_percent:.1f}%</span>
                    <span style="font-size: 0.9em; font-weight: bold; color: {color};">Reduction</span>
                </div>
                <div style="display: flex; align-items: center; justify-content: center;">
                    <div style="text-align: center; margin-right: 5px;">
                        <div style="
                            border: 5px solid #A9A9A9;
                            border-radius: 50%; width: 90px; height: 90px;
                            display: flex; flex-direction: column; align-items: center; justify-content: center;
                        ">
                            <span style="font-size: 1em; font-weight: bold;">{conv_val:.3f}</span>
                            <span style="font-size: 0.7em;">{unit}</span>
                        </div>
                        <div style="font-size: 0.8em; font-weight: bold;">Conventional</div>
                    </div>
                    <div style="font-size: 2em; color: #A9A9A9; margin: 0 5px;">&#8594;</div>
                    <div style="text-align: center; margin-left: 5px;">
                        <div style="
                            border: 5px solid {color};
                            border-radius: 50%; width: 90px; height: 90px;
                            display: flex; flex-direction: column; align-items: center; justify-content: center;
                        ">
                            <span style="font-size: 1em; font-weight: bold; color: {color};">{regen_val:.3f}</span>
                            <span style="font-size: 0.7em; color: {color};">{unit}</span>
                        </div>
                        <div style="font-size: 0.8em; font-weight: bold; color: {color};">Regenerative</div>
                    </div>
                </div>
            </div>
            """
            return html

        # Create three columns for side-by-side layout
        col1, col2, col3 = st.columns(3)

        # Place each visualisation into a separate column
        with col1:
            st.markdown(create_full_impact_viz("Carbon Footprint", cf_conv, cf_regen, cf_reduction, "kg CO2eq"), unsafe_allow_html=True)
        with col2:
            st.markdown(create_full_impact_viz("Nitrogen Eutrophication", ep_n_conv, ep_n_regen, n_reduction, "kg N eq"), unsafe_allow_html=True)
        with col3:
            st.markdown(create_full_impact_viz("Phosphorus Eutrophication", ep_p_conv, ep_p_regen, p_reduction, "kg PO4 eq"), unsafe_allow_html=True)

    except (KeyError, Exception) as e:
        st.warning(f"Could not display environmental impact. Error: {e}")

def render_epcf_sim():
    # --- Environmental Simulation ---
    st.subheader("Environmental Simulation")
    try:
        with st.expander("Adjust Simulation Parameters"):
            st.write("Modify the chemical usage to see the impact on EP and Carbon Footprint.")
            
            # --- Conventional Inputs ---
            st.markdown("#### Conventional Farming Chemicals")
            default_conv_chemicals = [
                {"name": "DEEBAJ", "units": 2, "unit_weight": 25, "unit_class": "15-15-15"},
                {"name": "Agroharta", "units": 1, "unit_weight": 2, "unit_class": "15-15-15"},
                {"name": "GuangFong", "units": 5, "unit_weight": 25, "unit_class": "5-5-5"},
                {"name": "Foliar", "units": 1, "unit_weight": 1.5, "unit_class": "10-5-12"}
            ]
            
            sim_conv_chemicals = []
            for i, chem in enumerate(default_conv_chemicals):
                st.write(f"**{chem['name']}**")
                c1, c2, c3 = st.columns(3)
                units = c1.number_input("Units", value=chem['units'], key=f"conv_units_{i}")
                weight = c2.number_input("kg/unit", value=chem['unit_weight'], key=f"conv_weight_{i}")
                u_class = c3.text_input("Class (N-P-K)", value=chem['unit_class'], key=f"conv_class_{i}")
                sim_conv_chemicals.append({"name": chem['name'], "units": units, "unit_weight": weight, "unit_class": u_class})

            # --- Regenerative Inputs ---
            st.markdown("#### Regenerative Farming Agent")
            c1, c2 = st.columns(2)
            regen_units = c1.number_input("Units", value=6000, key="regen_units")
            regen_weight = c2.number_input("kg/unit", value=0.001, key="regen_weight")
            sim_regen_chemicals = [{"units": regen_units, "unit_weight": regen_weight}]

        # --- Simulation Calculation ---
        sim_ep_n_conv, sim_ep_p_conv, sim_cfp_conv = calc_ep_conv(sim_conv_chemicals)
        sim_ep_n_regen, sim_ep_p_regen, sim_cfp_regen = calc_ep_regen(sim_regen_chemicals)
        
        # --- Visualization ---
        st.markdown("---")
        st.markdown("<h4 style='text-align: center;'>Environmental KPI Effects</h4>", unsafe_allow_html=True)
        
        # Calculate percentage reduction based on simulated values
        sim_n_reduction = ((sim_ep_n_conv - sim_ep_n_regen) / sim_ep_n_conv) * 100 if sim_ep_n_conv > 0 else 0
        sim_p_reduction = ((sim_ep_p_conv - sim_ep_p_regen) / sim_ep_p_conv) * 100 if sim_ep_p_conv > 0 else 0
        sim_cf_reduction = ((sim_cfp_conv - sim_cfp_regen) / sim_cfp_conv) * 100 if sim_cfp_conv > 0 else 0

        # Define a new visualisation helper function to handle horizontal layout
        def create_sim_viz_horizontal(label, conv_val, regen_val, reduction_percent, unit):
            color = '#FF4136' if reduction_percent < 0 or (label == "Carbon Footprint" and reduction_percent < 0) else '#2ECC40'
            arrow = '↓' if reduction_percent < 0 else '↑'
            
            # The HTML structure for a single card
            html = f"""
            <div style="background-color: white; padding: 1.5rem; border-radius: 0.75rem; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1); text-align: center; border: 2px solid #ccc;">
                <h3 style="font-size: 1.2rem; font-weight: 700; margin-bottom: 0.5rem;">{label}</h3>
                <div style="
                    border: 8px solid {color};
                    border-radius: 50%;
                    width: 140px; height: 140px;
                    display: flex; flex-direction: column; align-items: center; justify-content: center;
                    margin: 0 auto 10px auto;
                ">
                    <span style="font-size: 1.5em; font-weight: bold; color: {color};">{abs(reduction_percent):.1f}% {arrow}</span>
                    <span style="font-size: 0.9em; font-weight: bold; color: {color};">Reduction</span>
                </div>
                <!-- Before and After Rings -->
                    <div style="display: flex; align-items: center; justify-content: center;">
                        <div style="text-align: center; margin-right: 5px;">
                            <div style="
                                border: 5px solid #A9A9A9;
                                border-radius: 50%; width: 90px; height: 90px;
                                display: flex; flex-direction: column; align-items: center; justify-content: center;
                            ">
                                <span style="font-size: 1em; font-weight: bold;">{conv_val:.3f}</span>
                                <span style="font-size: 0.7em;">{unit}</span>
                            </div>
                            <div style="font-size: 0.8em; font-weight: bold;">Conventional</div>
                        </div>
                        <div style="font-size: 2em; color: #A9A9A9; margin: 0 5px;">&#8594;</div>
                        <div style="text-align: center; margin-left: 5px;">
                            <div style="
                                border: 5px solid {color};
                                border-radius: 50%; width: 90px; height: 90px;
                                display: flex; flex-direction: column; align-items: center; justify-content: center;
                            ">
                                <span style="font-size: 1em; font-weight: bold; color: {color};">{regen_val:.3f}</span>
                                <span style="font-size: 0.7em; color: {color};">{unit}</span>
                            </div>
                            <div style="font-size: 0.8em; font-weight: bold; color: {color};">Regenerative</div>
                        </div>
                    </div>
            </div>
            """
            return html

        # Create three columns for a horizontal layout
        sim_col1, sim_col2, sim_col3 = st.columns(3)

        # Place each visualisation into a separate column
        with sim_col1:
            st.markdown(create_sim_viz_horizontal("Carbon Footprint", sim_cfp_conv, sim_cfp_regen, sim_cf_reduction, "kg CO2eq"), unsafe_allow_html=True)
        with sim_col2:
            st.markdown(create_sim_viz_horizontal("Nitrogen Eutrophication", sim_ep_n_conv, sim_ep_n_regen, sim_n_reduction, "kg N eq"), unsafe_allow_html=True)
        with sim_col3:
            st.markdown(create_sim_viz_horizontal("Phosphorus Eutrophication", sim_ep_p_conv, sim_ep_p_regen, sim_p_reduction, "kg PO4 eq"), unsafe_allow_html=True)


    except (KeyError, IndexError, Exception) as e:
        st.warning(f"Could not perform environmental simulation. Error: {e}")

def render_harvest_composition():
    # --- Harvest Composition ---
    st.subheader("Harvest Composition Comparison")
    
    # Custom legend under the title
    st.markdown("""
        <div style="text-align: center;">
            <span style="color: #004B00;">■</span> Grade A (kg) &nbsp; &nbsp;
            <span style="color: #008A00;">■</span> Grade B (kg)
        </div>
    """, unsafe_allow_html=True)
    
    try:
        # Create two columns to place charts side by side
        col1, col2 = st.columns(2)

        # --- Limau Nipis Chart ---
        # Melt the nipis dataframe to prepare for stacking
        melted_nipis_df = yield_nipis_df.melt(
            id_vars=['Farming Method'],
            value_vars=['Grade A (kg)', 'Grade B (kg)'],
            var_name='Grade',
            value_name='Harvest (kg)'
        )

        fig_harvest_nipis = px.bar(
            melted_nipis_df,
            x='Farming Method',
            y='Harvest (kg)',
            color='Grade',
            barmode='stack',
            title='Limau Nipis',
            text_auto='.2f',
            color_discrete_map={
                'Grade A (kg)': "#004B00",
                'Grade B (kg)': "#008A00"
            }
        )
        fig_harvest_nipis.update_layout(
            xaxis_title=None,
            yaxis_title='Total Harvest (kg)',
            showlegend=False,  # Hide the chart's default legend
            height=400,
            bargap=0.45
        )
        
        # Place the first chart in the first column
        with col1:
            st.plotly_chart(fig_harvest_nipis, use_container_width=True)

        # --- Limau Kasturi Chart ---
        # Melt the kasturi dataframe
        melted_kasturi_df = yield_kasturi_df.melt(
            id_vars=['Farming Method'],
            value_vars=['Grade A (kg)', 'Grade B (kg)'],
            var_name='Grade',
            value_name='Harvest (kg)'
        )

        fig_harvest_kasturi = px.bar(
            melted_kasturi_df,
            x='Farming Method',
            y='Harvest (kg)',
            color='Grade',
            barmode='stack',
            title='Limau Kasturi',
            text_auto='.2f',
            color_discrete_map={
                'Grade A (kg)': '#004B00',
                'Grade B (kg)': '#008A00'
            }
        )
        fig_harvest_kasturi.update_layout(
            xaxis_title=None,
            yaxis_title=None,
            showlegend=False,  # Hide the chart's default legend
            height=400,
            bargap=0.45
        )
        
        # Place the second chart in the second column
        with col2:
            st.plotly_chart(fig_harvest_kasturi, use_container_width=True)

    except (IndexError, KeyError, ValueError, Exception) as e:
        st.warning(f"Could not create harvest composition chart. Error: {e}")

def render_yield_comparison():
    # --- Disaggregated Yield Comparison ---
    st.markdown(f"""<div style="text-align: center;"><div style="font-weight: bold; font-size: 1.4em;">Yield per site for Regenerative vs Conventional</div></div>""", unsafe_allow_html=True)

    try:
        # Get the yield values
        nipis_conv = disaggregation_df.loc['Limau Nipis', 'Conventional Farming']
        nipis_regen = disaggregation_df.loc['Limau Nipis', 'Regenerative Farming']
        kasturi_conv = disaggregation_df.loc['Limau Kasturi', 'Conventional Farming']
        kasturi_regen = disaggregation_df.loc['Limau Kasturi', 'Regenerative Farming']

        # Calculate percentage increase
        nipis_increase = ((nipis_regen - nipis_conv) / nipis_conv) * 100
        kasturi_increase = ((kasturi_regen - kasturi_conv) / kasturi_conv) * 100

        # --- Custom HTML Visualization Function ---
        def create_full_impact_viz(label, conv_val, regen_val, reduction_percent, unit):
            color = '#1E90FF' if reduction_percent > 0 else '#FF4136'
            html = f"""
            <div style="text-align: center;">
                <div style="font-weight: bold; font-size: 1em; margin-bottom: 10px;">{label}</div>
                <div style="
                    border: 8px solid {color};
                    border-radius: 50%; width: 140px; height: 140px;
                    display: flex; flex-direction: column; align-items: center; justify-content: center;
                    margin: 0 auto 10px auto;
                ">
                    <span style="font-size: 1.5em; font-weight: bold; color: {color};">{reduction_percent:.1f}%</span>
                    <span style="font-size: 0.9em; font-weight: bold; color: {color};">Increase</span>
                </div>
                <div style="display: flex; align-items: center; justify-content: center;">
                    <div style="text-align: center; margin-right: 5px;">
                        <div style="
                            border: 5px solid #A9A9A9;
                            border-radius: 50%; width: 85px; height: 85px;
                            display: flex; flex-direction: column; align-items: center; justify-content: center;
                        ">
                            <span style="font-size: 1em; font-weight: bold;">{conv_val:.1f}</span>
                            <span style="font-size: 0.7em;">{unit}</span>
                        </div>
                        <div style="font-size: 0.8em; font-weight: bold;">Conventional</div>
                    </div>
                    <div style="font-size: 2em; color: #A9A9A9; margin: 0 5px;">&#8594;</div>
                    <div style="text-align: center; margin-left: 5px;">
                        <div style="
                            border: 5px solid {color};
                            border-radius: 50%; width: 85px; height: 85px;
                            display: flex; flex-direction: column; align-items: center; justify-content: center;
                        ">
                            <span style="font-size: 0.8em; font-weight: bold; color: {color};">{regen_val:.1f}</span>
                            <span style="font-size: 0.7em; color: {color};">{unit}</span>
                        </div>
                        <div style="font-size: 0.8em; font-weight: bold; color: {color};">Regenerative</div>
                    </div>
                </div>
            </div>
            """
            return html
        
        # Display as metrics
        sub_col1, sub_col2 = st.columns(2)
        with sub_col1:
            st.markdown(create_full_impact_viz("Limau Nipis", nipis_conv, nipis_regen, nipis_increase, "kg"), unsafe_allow_html=True)
        with sub_col2:
            st.markdown(create_full_impact_viz("Limau Kasturi", kasturi_conv, kasturi_regen, kasturi_increase, "kg"), unsafe_allow_html=True)

    except (KeyError, Exception) as e:
        st.warning(f"Could not calculate yield uplift. Error: {e}")
        
def render_financial_sim():
    # --- Financial Simulation ---
    st.subheader("Financial Simulation")
    try:
        # --- Calculation Function ---
        def calculate_rf_margin(data, months, prices, costs):
            # Get the last x months of data
            last_x_months_data = data.tail(months)

            # Calculate total harvest
            total_harvest_A = last_x_months_data['Grade A (kg)'].sum()
            total_harvest_B = last_x_months_data['Grade B (kg)'].sum()

            # Calculate revenue
            revenue = (total_harvest_A * prices['A']) + (total_harvest_B * prices['B'])
            
            # Calculate total cost
            total_cost = costs * months
            
            # Calculate R/F Margin
            rf_margin = revenue / total_cost if total_cost > 0 else 0
            return rf_margin

        # --- Inputs for Simulation ---
        with st.expander("Adjust Simulation Parameters"):
            st.write("Use the sliders for quick adjustments or the input boxes for precise values.")
            # months_to_simulate = st.slider("Number of Months to Simulate", 1, 12, 6)
            months_to_simulate = 6
            
            sim_col1, sim_col2 = st.columns(2)
            with sim_col1:
                st.markdown("#### Sale Prices (RM/kg)")
                # Helper function for combined slider and number input
                def create_input_slider(label, min_val, max_val, default_val, key):
                    c1, c2 = st.columns([2,1])
                    with c1:
                        slider_val = st.slider(label, float(min_val), float(max_val), float(default_val), key=f"{key}_slider")
                    with c2:
                        num_val = st.number_input("", value=slider_val, key=f"{key}_num", label_visibility="collapsed", format="%.2f")
                    return num_val

                price_nipis_a = create_input_slider("Limau Nipis - Grade A", 5.0, 15.0, 8.21, "pna")
                price_nipis_b = create_input_slider("Limau Nipis - Grade B", 4.0, 12.0, 7.14, "pnb")
                price_kasturi_a = create_input_slider("Limau Kasturi - Grade A", 5.0, 15.0, 7.57, "pka")
                price_kasturi_b = create_input_slider("Limau Kasturi - Grade B", 4.0, 12.0, 6.85, "pkb")
            with sim_col2:
                st.markdown("#### Monthly Costs (RM)")
                cost_conv = create_input_slider("Conventional Farming", 500.0, 1500.0, 888.3, "cc")
                cost_regen = create_input_slider("Regenerative Farming", 500.0, 1500.0, 710.0, "cr")

        # --- Data Preparation ---
        # Split the main harvest dataframe into four smaller ones
        nipis_conv_data = plant_harvest_df.iloc[:, 1:3].dropna().rename(columns={'Grade A (kg)': 'Grade A (kg)', 'Grade B (kg)': 'Grade B (kg)'})
        nipis_regen_data = plant_harvest_df.iloc[:, 5:7].dropna().rename(columns={'Grade A (kg).1': 'Grade A (kg)', 'Grade B (kg).1': 'Grade B (kg)'})
        kasturi_conv_data = plant_harvest_df.iloc[:, 9:11].dropna().rename(columns={'Grade A (kg).2': 'Grade A (kg)', 'Grade B (kg).2': 'Grade B (kg)'})
        kasturi_regen_data = plant_harvest_df.iloc[:, 13:15].dropna().rename(columns={'Grade A (kg).3': 'Grade A (kg)', 'Grade B (kg).3': 'Grade B (kg)'})
        
        # --- Historical Calculation ---
        hist_prices_nipis = {'A': 8.21, 'B': 7.14}
        hist_prices_kasturi = {'A': 7.57, 'B': 6.85}
        hist_costs = {'conv': 888.3, 'regen': 710.0}
        
        hist_rev_conv = (calculate_rf_margin(nipis_conv_data, 6, hist_prices_nipis, hist_costs['conv']) * hist_costs['conv'] * 6) + \
                            (calculate_rf_margin(kasturi_conv_data, 6, hist_prices_kasturi, hist_costs['conv']) * hist_costs['conv'] * 6)
        hist_margin_conv = hist_rev_conv / (hist_costs['conv'] * 6)

        hist_rev_regen = (calculate_rf_margin(nipis_regen_data, 6, hist_prices_nipis, hist_costs['regen']) * hist_costs['regen'] * 6) + \
                            (calculate_rf_margin(kasturi_regen_data, 6, hist_prices_kasturi, hist_costs['regen']) * hist_costs['regen'] * 6)
        hist_margin_regen = hist_rev_regen / (hist_costs['regen'] * 6)

        # --- Simulated Calculation ---
        sim_prices_nipis = {'A': price_nipis_a, 'B': price_nipis_b}
        sim_prices_kasturi = {'A': price_kasturi_a, 'B': price_kasturi_b}
        sim_costs = {'conv': cost_conv, 'regen': cost_regen}

        sim_rev_conv = (calculate_rf_margin(nipis_conv_data, months_to_simulate, sim_prices_nipis, sim_costs['conv']) * sim_costs['conv'] * months_to_simulate) + \
                        (calculate_rf_margin(kasturi_conv_data, months_to_simulate, sim_prices_kasturi, sim_costs['conv']) * sim_costs['conv'] * months_to_simulate)
        sim_margin_conv = sim_rev_conv / (sim_costs['conv'] * months_to_simulate)

        sim_rev_regen = (calculate_rf_margin(nipis_regen_data, months_to_simulate, sim_prices_nipis, sim_costs['regen']) * sim_costs['regen'] * months_to_simulate) + \
                            (calculate_rf_margin(kasturi_regen_data, months_to_simulate, sim_prices_kasturi, sim_costs['regen']) * sim_costs['regen'] * months_to_simulate)
        sim_margin_regen = sim_rev_regen / (sim_costs['regen'] * months_to_simulate)

        # --- Visualization ---
        st.markdown("---")
        st.markdown("<h4 style='text-align: center;'>Revenue/Fertiliser Margin Change</h4>", unsafe_allow_html=True)

        # --- Visualization ---
        def create_margin_change_viz(label, hist_val, sim_val):
            change_percent = ((sim_val - hist_val) / hist_val) * 100 if hist_val > 0 else 0
            color = '#2ECC40' if change_percent >= 0 else '#FF4136'
            arrow = '↑' if change_percent >= 0 else '↓'

            html = f"""
            <div style="background-color: white; padding: 1.5rem; border-radius: 0.75rem; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1); text-align: center; border: 2px solid #ccc;">
                <h3 style="font-size: 1.2rem; font-weight: 700; margin-bottom: 0.5rem;">{label}</h3>
                <div style="
                    border: 8px solid {color};
                    border-radius: 50%;
                    width: 140px; height: 140px;
                    display: flex; flex-direction: column; align-items: center; justify-content: center;
                    margin: 0 auto 10px auto;
                ">
                    <span style="font-size: 1.5em; font-weight: bold; color: {color};">{change_percent:.1f}% {arrow}</span>
                    <span style="font-size: 0.9em; font-weight: bold; color: {color};">Change</span>
                </div>
                <!-- Before and After Rings -->
                <div style="display: flex; align-items: center; justify-content: center;">
                    <div style="text-align: center; margin-right: 5px;">
                        <div style="
                            border: 5px solid #A9A9A9;
                            border-radius: 50%; width: 90px; height: 90px;
                            display: flex; flex-direction: column; align-items: center; justify-content: center;
                        ">
                            <span style="font-size: 1em; font-weight: bold;">{hist_val:.2f}</span>
                        </div>
                        <div style="font-size: 0.8em; font-weight: bold;">Historical</div>
                    </div>
                    <div style="font-size: 2em; color: #A9A9A9; margin: 0 5px;">&#8594;</div>
                    <div style="text-align: center; margin-left: 5px;">
                        <div style="
                            border: 5px solid {color};
                            border-radius: 50%; width: 90px; height: 90px;
                            display: flex; flex-direction: column; align-items: center; justify-content: center;
                        ">
                            <span style="font-size: 1em; font-weight: bold; color: {color};">{sim_val:.2f}</span>
                        </div>
                        <div style="font-size: 0.8em; font-weight: bold; color: {color};">Simulated</div>
                    </div>
                </div>
            </div>
            """
            return html

        viz_col1, viz_col2 = st.columns(2)
        with viz_col1:
            st.markdown(create_margin_change_viz("Conventional", hist_margin_conv, sim_margin_conv), unsafe_allow_html=True)
        with viz_col2:
            st.markdown(create_margin_change_viz("Regenerative", hist_margin_regen, sim_margin_regen), unsafe_allow_html=True)


    except (KeyError, IndexError, Exception) as e:
        st.warning(f"Could not perform financial simulation. Error: {e}")

def render_monthly_yield_comparison(plant_harvest_df):
    """
    Renders a new widget to compare a specific month's yield against the overall average.
    """
    st.subheader("Monthly Yield Comparison")

    try:
        # Pre-process the dataframe for easier calculations
        df = plant_harvest_df.copy()
        df['Month'] = pd.to_datetime(df['Month'])
        
        # Consolidate yield data
        df['Conv Total Yield'] = df['Grade A (kg)'] + df['Grade B (kg)'] + df['Grade A (kg).2'] + df['Grade B (kg).2']
        df['Regen Total Yield'] = df['Grade A (kg).1'] + df['Grade B (kg).1'] + df['Grade A (kg).3'] + df['Grade B (kg).3']
        
        # Calculate the overall averages
        avg_conv_yield = df['Conv Total Yield'].mean()
        avg_regen_yield = df['Regen Total Yield'].mean()

        # Month Picker
        months = df['Month'].dt.strftime('%B %Y').tolist()
        selected_month = st.selectbox("Select a month to compare", months)

        

        # Get the selected month's data
        selected_date = pd.to_datetime(selected_month)
        monthly_data = df[df['Month'] == selected_date].iloc[0]
        monthly_conv_yield = monthly_data['Conv Total Yield']
        monthly_regen_yield = monthly_data['Regen Total Yield']

        # Calculate difference from average
        conv_diff_pct = ((monthly_conv_yield - avg_conv_yield) / avg_conv_yield) * 100
        regen_diff_pct = ((monthly_regen_yield - avg_regen_yield) / avg_regen_yield) * 100
        
        # Define colours based on performance
        conv_color = '#2ECC40' if conv_diff_pct > 0 else '#FF4136'
        regen_color = '#2ECC40' if regen_diff_pct > 0 else '#FF4136'


        # Custom HTML to display the results in a card-like format
        st.markdown(f"""
        <div style="display: flex; justify-content: space-around; gap: 20px;">
            <!-- Conventional Card -->
            <div style="
                flex: 1;
                background-color: white;
                padding: 1.5rem;
                border-radius: 0.75rem;
                box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
                text-align: center;
                border: 5px solid {conv_color};
            ">
                <h3 style="font-size: 1.5rem; font-weight: 700;">Conventional Farming</h3>
                <p style="font-size: 1.8rem; font-weight: 700; color: #333;">{monthly_conv_yield:.2f} kg</p>
                <div style="font-size: 1em; color: {conv_color}; font-weight: bold;">
                    {conv_diff_pct:.1f}% vs Average
                </div>
                <div style="font-size: 0.8em; color: #666; margin-top: 10px;">
                    Average: {avg_conv_yield:.2f} kg
                </div>
            </div>
            <!-- Regenerative Card -->
            <div style="
                flex: 1;
                background-color: white;
                padding: 1.5rem;
                border-radius: 0.75rem;
                box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
                text-align: center;
                border: 5px solid {regen_color};
            ">
                <h3 style="font-size: 1.5rem; font-weight: 700;">Regenerative Farming</h3>
                <p style="font-size: 1.8rem; font-weight: 700; color: #333;">{monthly_regen_yield:.2f} kg</p>
                <div style="font-size: 1em; color: {regen_color}; font-weight: bold;">
                    {regen_diff_pct:.1f}% vs Average
                </div>
                <div style="font-size: 0.8em; color: #666; margin-top: 10px;">
                    Average: {avg_regen_yield:.2f} kg
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Error calculating monthly yield comparison: {e}")


def render_chatbot_page():
    """Renders the chatbot interface within the Streamlit app."""
    st.markdown("### AI Chatbot")
    st.write("Ask a question about your documents and get a conversational answer.")
    
    # Initialize the chat message history
    if "messages" not in st.session_state:
        st.session_state.messages = []
        
    # Display chat messages from history on app rerun
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Accept user input
    if query := st.chat_input("Ask a question..."):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": query})
        # Display user message in chat message container
        with st.chat_message("user"):
            st.markdown(query)
            
        # Display assistant response in chat message container
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    # Make a POST request to the API
                    response = requests.post(CHATBOT_API_URL, json={"question": query})
                    
                    if response.status_code == 200:
                        api_response = response.json()
                        answer = api_response.get("answer", "No answer found.")
                        sources = api_response.get("sources", [])
                        
                        st.markdown(answer)
                        
                        # (Optional) Display source documents from the API response
                        if sources:
                            st.markdown("---")
                            st.markdown("##### Sources")
                            for doc in sources:
                                st.markdown(f"- **Source:** {doc.get('source', 'N/A')}, **Page:** {doc.get('page', 'N/A')}")
                    else:
                        st.error(f"Error from chatbot API: {response.status_code} - {response.text}")
                
                except requests.exceptions.ConnectionError:
                    st.error("Could not connect to the chatbot API. Please ensure the API server is running.")
                except Exception as e:
                    st.error(f"An unexpected error occurred: {e}")


cost_conv = 888.3
cost_regen = 710.0
cost_reduction_pct = ((cost_conv - cost_regen) / cost_conv) * 100 if cost_conv > 0 else 0

# --- Yield Increase ---
total_conv_yield = plant_harvest_df.iloc[:, [1,2,9,10]].sum().sum()
total_regen_yield = plant_harvest_df.iloc[:, [5,6,13,14]].sum().sum()
yield_increase_pct = ((total_regen_yield - total_conv_yield) / total_conv_yield) * 100 if total_conv_yield > 0 else 0

# --- Revenue Increase ---
prices = {'nipis_A': 8.21, 'nipis_B': 7.14, 'kasturi_A': 7.57, 'kasturi_B': 6.85}
total_conv_rev = (plant_harvest_df.iloc[:, 1].sum() * prices['nipis_A'] + 
                  plant_harvest_df.iloc[:, 2].sum() * prices['nipis_B'] +
                  plant_harvest_df.iloc[:, 9].sum() * prices['kasturi_A'] +
                  plant_harvest_df.iloc[:, 10].sum() * prices['kasturi_B'])

total_regen_rev = (plant_harvest_df.iloc[:, 5].sum() * prices['nipis_A'] +
                   plant_harvest_df.iloc[:, 6].sum() * prices['nipis_B'] +
                   plant_harvest_df.iloc[:, 13].sum() * prices['kasturi_A'] +
                   plant_harvest_df.iloc[:, 14].sum() * prices['kasturi_B'])
revenue_increase_pct = ((total_regen_rev - total_conv_rev) / total_conv_rev) * 100 if total_conv_rev > 0 else 0

# --- Gross Profit Increase ---
total_conv_cost = cost_conv * 6
total_regen_cost = cost_regen * 6
conv_gross_profit = total_conv_rev - total_conv_cost
regen_gross_profit = total_regen_rev - total_regen_cost
gp_increase_pct = ((regen_gross_profit - conv_gross_profit) / conv_gross_profit) * 100 if conv_gross_profit > 0 else 0

# # --- Header ---
# st.markdown("""
#     <header style="margin-bottom: 2rem;">
#         <h1 style="font-size: 2.25rem; font-weight: 700; color: #1f2937;">Comparative Analysis Dashboard</h1>
#         <p style="color: #6b7280; margin-top: 0.25rem;">An overview of key metrics and simulations for regenerative agriculture.</p>
#     </header>
# """, unsafe_allow_html=True)

# --- Page Navigation in Sidebar ---
page = st.sidebar.radio("Choose a page", ["Dashboard Overview", "Simulations", "Chatbot"])

if page == "Dashboard Overview":
    
    # --- Metric Cards ---
    container1 = st.container()
    container2 = st.container()
    container3 = st.container()
    with container1:
        cols = st.columns(4)
        metrics = [
            {"label": "Total Cost", "value": f"{cost_reduction_pct:.1f}% ↓", "color": "#4a90e2"},
            {"label": "Total Yield", "value": f"{yield_increase_pct:.1f}% ↑", "color": "#7ed321"},
            {"label": "Total Revenue", "value": f"{revenue_increase_pct:.1f}% ↑", "color": "#50e3c2"},
            {"label": "Gross Profit", "value": f"{gp_increase_pct:.1f}% ↑", "color": "#f5a623"},
        ]
        for i, metric in enumerate(metrics):
            with cols[i]:
                st.markdown(f"""
                <div class="metric-card" style="background-color: {metric['color']};">
                    <p>{metric['value']}</p>
                    <h3>{metric['label']}</h3>
                </div>
                """, unsafe_allow_html=True)
        
        st.markdown("<hr style='margin: 0.7rem 0;'>", unsafe_allow_html=True)
    
    with container2:
        # --- Main Dashboard Grid ---
        cols1 = st.columns(3)
        with cols1[0]:
            render_cost_comparison()
        with cols1[1]:
            render_harvest_composition()
        with cols1[2]:
            render_monthly_yield_comparison(plant_harvest_df)
        
        st.markdown("<hr style='margin: 0rem;'>", unsafe_allow_html=True)
    
    with container3:
        col = st.columns(2)
        with col[0]:
            render_ep_reduction()
        with col[1]:
            column1, column2= st.columns((1.2,1))
            with column1:
                render_yield_comparison()
            with column2:
                render_sqi()


elif page == "Simulations":
    st.markdown("### Simulation Centre")
    st.write("Adjust parameters to forecast financial and environmental outcomes.")
    
    col1, gap, col2 = st.columns((2,0.2,3))
    with col1:
        render_financial_sim()
    with col2:
        render_epcf_sim()


elif page == "Chatbot":
    st.markdown("### Chatbot")
    st.write("Interact with our AI chatbot for insights and assistance.")
    render_chatbot_page()