# Import necessary libraries
import pandas as pd
import plotly.graph_objects as go

# Method to remove unnamed columns from datasets
def remove_unnamed(df):
    return df.loc[:, ~df.columns.str.contains('^Unnamed')]

# Method to extract data from source clean
def read_data(file_path):
    return remove_unnamed(pd.read_csv(file_path))

# Method to calculate the expected charge
def calculate_expected_charge(row, courier_company_rates):
    fwd_category = 'fwd_' + row['Delivery Zone As Per ABC']
    fwd_fixed = courier_company_rates.at[0, fwd_category + '_fixed']
    fwd_additional = courier_company_rates.at[0, fwd_category + '_additional']
    rto_category = 'rto_' + row['Delivery Zone As Per ABC']
    rto_fixed = courier_company_rates.at[0, rto_category + '_fixed']
    rto_additional = courier_company_rates.at[0, rto_category + '_additional']

    weight_slab = row['Weight Slab As Per ABC']

    if row['Type of Shipment'] == 'Forward charges':
        additional_weight = max(0, (weight_slab - 0.5) / 0.5)
        return fwd_fixed + additional_weight * fwd_additional
    elif row['Type of Shipment'] == 'Forward and RTO charges':
        additional_weight = max(0, (weight_slab - 0.5) / 0.5)
        return fwd_fixed + additional_weight * (fwd_additional + rto_additional)
    else:
        return 0

# Method to generate final output in determining charge difference
def calculate_summary(df_new):
    total_correctly_charged = len(df_new[df_new['Difference (Rs.)'] == 0])
    total_overcharged = len(df_new[df_new['Difference (Rs.)'] > 0])
    total_undercharged = len(df_new[df_new['Difference (Rs.)'] < 0])

    amount_overcharged = abs(df_new[df_new['Difference (Rs.)'] > 0]['Difference (Rs.)'].sum())
    amount_undercharged = df_new[df_new['Difference (Rs.)'] < 0]['Difference (Rs.)'].sum()
    amount_correctly_charged = df_new[df_new['Difference (Rs.)'] == 0]['Expected Charge as per ABC'].sum()

    summary_data = {'Description': ['Total Orders where ABC has been correctly charged',
                                    'Total Orders where ABC has been overcharged',
                                    'Total Orders where ABC has been undercharged'],
                    'Count': [total_correctly_charged, total_overcharged, total_undercharged],
                    'Amount (Rs.)': [amount_correctly_charged, amount_overcharged, amount_undercharged]}

    df_summary = pd.DataFrame(summary_data)
    return df_summary

# Method to generate visual output
def plot_pie_chart(df_summary):
    fig = go.Figure(data=go.Pie(labels=df_summary['Description'],
                                values=df_summary['Count'],
                                textinfo='label+percent',
                                hole=0.4))
    fig.update_layout(title='Proportion')
    fig.show()

# Read data from source files
order_report = read_data('b2b/Order-Report.csv')
sku_master = read_data('b2b/SKU-Master.csv')
pincode_mapping = read_data('b2b/pincodes.csv')
courier_invoice = read_data('b2b/Invoice.csv')
courier_company_rates = read_data('b2b/Courier-Company-Rates.csv')

# Display data preview
dfs = [order_report, sku_master, pincode_mapping, courier_invoice, courier_company_rates]
for df in dfs:
    print(df.head())

# Check for missing values
for df in dfs:
    print(f"\nMissing values in {df}:")
    print(df.isnull().sum())

# Remove unnamed columns
order_report = remove_unnamed(order_report)
sku_master = remove_unnamed(sku_master)
pincode_mapping = remove_unnamed(pincode_mapping)

# Merge the Order Report and SKU Master based on SKU
merged_data = pd.merge(order_report, sku_master, on='SKU')
print(merged_data.head())

# Rename column
merged_data.rename(columns={'ExternOrderNo': 'Order ID'}, inplace=True)

# Merge the courier invoice and pincode mapping dataset
abc_courier = pincode_mapping.drop_duplicates(subset=['Customer Pincode'])
courier_abc = courier_invoice[['Order ID', 'Customer Pincode', 'Type of Shipment']]
pincodes = courier_abc.merge(abc_courier, on='Customer Pincode')
print(pincodes.head())

# Merge both merges
merger = merged_data.merge(pincodes, on='Order ID')

# Convert weight from grams to kilograms
merger['Weights (Kgs)'] = merger['Weight (g)'] / 1000

# Generate weight slab column
merger['Weight Slab (KG)'] = merger['Weights (Kgs)'].apply(lambda weight: int(weight) + 0.5 if weight % 1 > 0.5 else int(weight))
courier_invoice['Weight Slab Charged by Courier Company'] = courier_invoice['Charged Weight'].apply(lambda weight: int(weight) + 0.5 if weight % 1 > 0.5 else int(weight))

# Rename columns
courier_invoice.rename(columns={'Zone': 'Delivery Zone Charged by Courier Company'}, inplace=True)
merger.rename(columns={'Zone': 'Delivery Zone As Per ABC', 'Weight Slab (KG)': 'Weight Slab As Per ABC'}, inplace=True)

# Calculate expected charge
merger['Expected Charge as per ABC'] = (
    merger.apply(lambda row: calculate_expected_charge(row, courier_company_rates), axis=1)
)

# Merge new data frame with the courier invoice
merged_output = merger.merge(courier_invoice, on='Order ID')

# Calculate the differences in charges and expected charges for each order
merged_output['Difference (Rs.)'] = merged_output['Billing Amount (Rs.)'] - merged_output['Expected Charge as per ABC']
df_new = merged_output[['Order ID', 'Difference (Rs.)', 'Expected Charge as per ABC']]
print(df_new.head())

# Calculate the total orders in each category
df_summary = calculate_summary(df_new)

# Display summary
print(df_summary)

# Plot a pie chart for the summary
plot_pie_chart(df_summary)
