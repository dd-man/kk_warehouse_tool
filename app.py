# Import necessary libraries
df_style = df.style.format({
    'your_numeric_column_1': '{:.2f}',
    'your_numeric_column_2': '{:.2f}',
    # Add additional numeric columns here
})

# continue with displaying df_style