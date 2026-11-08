import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv("sample.csv")

print(df.head(5))
print(df.shape)
print(df.dtypes)
print(df.isna().sum())

#print(df.groupby("mass_g")["extension_cm"].mean())

def summarize_data(df, group_column, measurement_column):
    for column in [group_column, measurement_column]:
        if column not in df.columns:
            raise ValueError(f"Column '{column}' was not found in the dataset.")

    if not pd.api.types.is_numeric_dtype(df[measurement_column]):
        raise ValueError(f"Column '{measurement_column}' does not have numeric values")
        
    return (df.groupby(group_column)[measurement_column].agg(["mean", "std", "count"]))

summary = summarize_data(df, 'mass_g', 'extension_cm')
print(summary)

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