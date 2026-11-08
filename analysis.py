import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st
import time

st.title("EvidenceLab")
st.write("Upload experimental data to explore your results.")

uploaded_file = st.file_uploader("Upload CSV file", type="csv")

if uploaded_file is None:
    st.info("Uplaod a CSV file to begin")
    st.stop()

df = pd.read_csv(uploaded_file)

#print(df.groupby("mass_g")["extension_cm"].mean())

def summarize_data(df, group_column, measurement_column):
    for column in [group_column, measurement_column]:
        if column not in df.columns:
            raise ValueError(f"Column '{column}' was not found in the dataset.")

    if not pd.api.types.is_numeric_dtype(df[measurement_column]):
        raise ValueError(f"Column '{measurement_column}' does not have numeric values")
        
    return (df.groupby(group_column)[measurement_column].agg(["mean", "std", "count"]))

summary = summarize_data(df, 'mass_g', 'extension_cm')
st.write(summary)
st.line_chart(summary)

missing = df.isna().sum()

for column, count in missing.items():
    if count > 0:
        print(f"Warning: {column} has {count} missing value(s).")

plt.errorbar(
    x= summary.index,
    y= summary['mean'],
    yerr= summary['std'],
    fmt="o",
    capsize=4
)

plt.xlabel("Mass (g)")
plt.ylabel("Mean extension (cm)")
plt.title("Effect of mass on extension")
plt.tight_layout()
plt.show()