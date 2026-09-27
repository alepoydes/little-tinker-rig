# Two-wheel training base · SPIKE Prime 45678

The 20-part model uses the hub as its chassis. Coordinate units are LDU (0.4 mm);
up is −Y and forward is +Z. The wheel centers are at X = ±170, giving a 136 mm
track. Wheel diameter is 56 mm. Wheels and support ball reach Y = 60.

The moving elements and their mating features are explicit:

- Medium motors mount against the hub's X = ±70 side faces. Their inner mounting
  holes at local `(0, 30, -20)` and `(0, 30, 140)` align with the hub's lowest
  side holes at Y = −10, Z = ±80. Pins have their axes along X.
- Motor outputs face outward at X = ±150. Three-module axles, centered at ±160,
  pass through each output and its wheel. The wheel's inner face is at ±152.5,
  leaving 2.5 LDU clearance from the motor face.
- The ball carrier mounts to the hub's rear face Z = −110. Its upper pair of
  holes aligns with X = ±40, Y = −30; the carrier is centered at Z = −120.
- The seven-module front beam mounts at Z = 120 through its X = ±40 holes to
  the hub's front bottom holes. Its end holes at X = ±60 hold the sensor's rear
  holes. Sensor eyes face +Z. Connections touch at Z = 110 and Z = 130.

The assembly geometry and mating coordinates are checked digitally. Physical
fit, cable routing and driving calibration still need a check on a real set.
Cables are described in the instructions; their flexible geometry is not modeled.
The motor port labels A/B and sensor D refer to the hub's molded labels.

Only the original robot arrangement and lesson annotations are stored here.
`robot.json` pins the external LDraw archive by release and SHA-256. LittleTinker Rig
downloads it to the user's cache and reads the required ZIP members directly.
An offline project export includes a minimal parts ZIP with author notices and
licenses. See [LICENSE.txt](LICENSE.txt).
