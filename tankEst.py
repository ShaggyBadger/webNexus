from math import pi
from math import acos
from math import sin
from math import radians
import matplotlib.pyplot as plt

max_v = 9816
measured_h = 29.11
measured_v = 2707

def find_length(maxV, r):
v = maxV * 231

L = v / (pi * r * r)
return L

def generate_r_L_pairs():
pairs = {}

for i in range(10, 2001):
r = i / 10
if r >= measured_h:
L = find_length(max_v, r)
pairs[r] = L

return pairs

def calculate_volume(r, L):
# find verticle side
vs = r - measured_h

# get theta
cf = vs / r # cos fraction
theta = 2 * (acos(cf) * (180 / pi))

# calculate sector area
sa = (pi * r * r) * (theta / 360)

# calculate triangle area
ta = 0.5 * r * r * sin(radians(theta))

# get 2D segment area
segment_area = sa - ta

# get 3D volume of segment
segment_volume = segment_area * L

# convert to gallons and return gallons
return segment_volume / 231

def main():
distance = None
best_fit_r = None
for i in range(10, 2001):
r = i / 10
if r < measured_h:
continue
L = find_length(max_v, r)

estemated_v = calculate_volume(r, L)


current_distance = abs(measured_v - estemated_v)

if distance is None:
distance = current_distance

if current_distance <= distance:
distance = current_distance
best_fit_r = r
print(distance, (r*2))












if __name__ == '__main__':
p = generate_r_L_pairs()

radii = []
volumes = []

for r, L in p.items():
segment_v = calculate_volume(r, L)
radii.append(r* 2)
volumes.append(segment_v)
print(r*2, round(segment_v), measured_v)

# Plot the curve
plt.plot(radii, volumes, label='Calculated Volume')

# Draw a line at the target ticket volume
plt.axhline(y=measured_v, color='r', linestyle='--', label=f'Ticket Vol ({measured_v})')

plt.xlabel('Radius (inches)')
plt.ylabel('Volume (gallons)')
plt.title('Finding the Target Tank Dimensions')
plt.legend()
plt.grid(True)
plt.show()

main()

