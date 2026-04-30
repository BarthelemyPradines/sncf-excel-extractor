from operator import imod
import pandas as pd
from src.excel_extractor.skeleton import extract_skeleton_from_excel



print('Original DF')
df = pd.read_excel('data/complex_test_workbook.xlsx', sheet_name=3)
print(df)

print('   ')
print('Skeleton DF')
skeleton = extract_skeleton_from_excel(file_path='data/complex_test_workbook.xlsx', sheet_index=3) 
print(skeleton)
