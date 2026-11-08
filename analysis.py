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
st.dataframe(df)

numeric_columns = df.select_dtypes(include="number").columns.tolist()

if len(numeric_columns) < 2:
    st.warning("Upload data with at least two numeric columns.")
    st.stop()

x_column = st.selectbox("X variable", numeric_columns)
y_column = st.selectbox("Y variable", numeric_columns, index=1)

if x_column == y_column:
    st.warning("Choose two different columns.")
    st.stop()


analysis_data = df[[x_column, y_column]].dropna()

if analysis_data.empty:
    st.warning("No rows contain values for both selected variables.")
    st.stop()

st.write(f"Measurements used: {len(analysis_data)}")
st.write(f"Excluded rows due to missing data: {len(df) - len(analysis_data)}")

def summarize_data(analysis_data, group_column, measurement_column):
    for column in [group_column, measurement_column]:
        if column not in analysis_data.columns:
            raise ValueError(f"Column '{column}' was not found in the dataset.")

    if not pd.api.types.is_numeric_dtype(analysis_data[measurement_column]):
        raise ValueError(f"Column '{measurement_column}' does not have numeric values")
        
    return (analysis_data.groupby(group_column)[measurement_column].agg(["mean", "std", "count"]))

summary = summarize_data(analysis_data, x_column, y_column)
st.write(summary)

missing = df.isna().sum()

for column, count in missing.items():
    if count > 0:
        st.write(f"Warning: {column} has {count} missing value(s).")

st.scatter_chart(analysis_data, x=x_column, y=y_column)

if len(analysis_data) < 3:
    st.info("At least three complete measurements are required here for correlation.")
elif (
    analysis_data[x_column].nunique() < 2
    or analysis_data[y_column].nunique() < 2
):
    st.info("Correlation is undefined when either variable is constant.")
else:
    r = analysis_data[x_column].corr(analysis_data[y_column])
    st.write(f"Pearson correlation (r): {r:.3f}")
    st.caption("Measures linear association; does not establish cause and effect.")