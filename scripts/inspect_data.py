import pandas as pd

for name in ["movies", "credits", "anime"]:
    df = pd.read_csv(f"data/{name}.csv")
    print("=" * 60)
    print(name.upper(), "| rows:", len(df))
    print(df.dtypes)
    print(df.head(2).T)
    print("Missing values:")
    print(df.isnull().sum())
