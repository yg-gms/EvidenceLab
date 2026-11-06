import pandas as pd

df = pd.read_csv("sample.csv")

print(df.head(5))
print(df.shape)
print(df.dtypes)
print(df.isna().sum())

#print(df.groupby("mass_g")["extension_cm"].mean())

def summarize_data(df, group_column, measurement_column):
    return (df.groupby(group_column)[measurement_column].agg(["mean", "std", "count"]))

summary = summarize_data(df, 'mass_g', 'extension_cm')
print(summary)

missing = df.isna().sum()

for column, count in missing.items():
    if count > 0:
        print(f"Warning: {column} has {count} missing value(s).")