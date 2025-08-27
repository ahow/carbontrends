#!/usr/bin/env python3

# The console shows: "Estimated carbon intensity for 3M year 2007: 0.266763 tCO2e/USD"
# But my calculation shows: "Raw 2007 estimate: 11.675570 tCO2e/USD"

# Let me check if there's a different calculation or capping going on

print("=== DISCREPANCY ANALYSIS ===")
print("Console log shows: 0.266763 tCO2e/USD for 3M 2007")
print("My calculation shows: 11.675570 tCO2e/USD raw estimate")
print("My calculation shows: 11.569137 tCO2e/USD capped estimate")
print()

# The console slope is different!
# Console: "slope=-0.00867783 tCO2e/USD/year, intercept=17.683172"
# My calc: "slope = -0.38192964 tCO2e/USD per year, intercept = 778.208358"

console_slope = -0.00867783
console_intercept = 17.683172

my_slope = -0.38192964
my_intercept = 778.208358

print("=== SLOPE COMPARISON ===")
print(f"Console slope: {console_slope:.8f}")
print(f"My slope: {my_slope:.8f}")
print(f"Console intercept: {console_intercept:.6f}")
print(f"My intercept: {my_intercept:.6f}")
print()

# Test both models for 2007
console_2007 = console_slope * 2007 + console_intercept
my_2007 = my_slope * 2007 + my_intercept

print("=== 2007 ESTIMATES ===")
print(f"Console model for 2007: {console_2007:.6f}")
print(f"My model for 2007: {my_2007:.6f}")
print(f"Console matches log: {abs(console_2007 - 0.266763) < 0.001}")
print()

print("=== EXPLANATION ===")
print("The console is using a different dataset or calculation method!")
print("The console slope is much smaller, suggesting a different trend calculation.")
print("This could be due to:")
print("1. Different units in the actual uploaded data")
print("2. Data preprocessing differences")
print("3. The sample_data.xlsx vs real uploaded data discrepancy")