from loaders import load_ai4i, load_cmapss, load_simulated

def clean(df):
    df = df.drop_duplicates()
    print(df.isnull().sum())

df = load_ai4i(filepath="E:\DrivePulseAI\data\failure_classification\raw\predictive_maintenance.csv")
df = load_simulated(filepath="E:\DrivePulseAI\data\anomly_detection\raw\drive.csv")