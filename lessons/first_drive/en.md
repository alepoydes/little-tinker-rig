# First drive · SPIKE Prime 45678

<a name="build"></a>

## Build a rolling base

Use SPIKE Prime **45678**, with Pybricks installed on the hub. Start with assembly steps **1–7**. Opening **Assembly** downloads the parts library once to the shared cache. After that, instructions work offline. To move the lesson to another computer without downloading again, use **File → Export lesson project with resources…**.

[Open Assembly](assembly:), rotate the robot and use **Next step**. The parts list tells you the quantity and the length of each axle or beam. **Recommended view** fits the parts assembled so far. A click selects a part.

After step 7, put the robot on a flat surface. Check that both wheels and the ball move freely and that the motor plugs are accessible. Mark this stage complete yourself; the app cannot detect whether the physical robot is assembled.

This is an original compact training base. Its connection geometry has been checked digitally; an adult should check that the real build is firm before its first drive.

<a name="connect"></a>

## Connect and check

Connect the **left motor to A** and the **right motor to B**. Look in the robot's forward direction: the wheels are at the front, the ball is behind them. Keep cables away from the wheels.

Use [Connect hub](connect:) (also available under **Hub → Connect…**) and choose Bluetooth or a virtual Inventor / SPIKE Prime hub. Then [open Hub and devices](devices:) and select **Open port monitor**. The stage check needs live motor readings on A and B. The virtual hub lets you practise without a physical robot.

Motor detection proves the ports are occupied by motors; it cannot distinguish left from right or verify cable routing. Briefly turn each motor in the monitor and check its wheel. Stop the monitor before running your program.

<a name="drive"></a>

## Your first journey

[Open the program](program:main.py) and place **Set up drive base** in it. Keep motor ports **A / B**, set wheel diameter to **56 mm**, and axle track to **136 mm** (between wheel centers).

Add **Drive straight** and set the distance to **200 mm**. **For this task** highlights the two suggested blocks; the full catalog remains available. Open the next hint if you get stuck. **Open starter program** creates a separate file with setup code once, then reopens that same file without replacing your work.

Put the robot on clear floor, connect it and press **Run**. Measure the journey. If the robot reverses, check that left and right motors match the ports and the model's forward direction. Mark complete after the robot moves forward and stops.

<a name="experiment"></a>

## Predict, change, try

Before each run, predict where the robot will stop. Change **200** to **400**, then try **−200**. What does the minus sign change?

A third block is now available: **Turn drive base**. Add a **90°** turn after the journey. Try swapping the two actions and compare the result.

You can return to an earlier task without losing any code. The full catalog stays available for experiments without erasing lesson progress.

<a name="sensor"></a>

## Add an obstacle sensor

Finish assembly steps **8–11**. The yellow front beam holds the ultrasonic distance sensor. Its round eyes point forward. Plug the sensor into **D**.

Use **Locate a device** in [Assembly](assembly:) to highlight the sensor and its hub port. In [Hub and devices](devices:), open the port monitor, move a large flat object in front of the sensor and watch the distance change. Objects that are tiny or angled may not reflect the sound well.

Mark complete after checking the mounting, cable and measurement.

<a name="stop"></a>

## Stop before the obstacle

Keep the robot setup. Remove the earlier journeys and turns (or move them to Scratch). Add **Connect sensor** (variant **Ultrasonic sensor**), with name **distance** and port **D**.

Add **Stop near object**. Use the drive base **drive**, sensor **distance**, threshold **100 mm**, and speed **100 mm/s**.

Put a large upright object in front of the robot. Run the program and keep **Stop** within reach. Check whether it stops about 100 mm from the sensor. Try a different threshold and predict the result.

On the virtual hub, change D to an ultrasonic sensor and adjust its distance in the monitor before running. The virtual sensor value is a controlled input, not a simulated room.

Save the `.ltr` project. Closing and reopening it keeps your program, Scratch, hints and completed stages. You can repeat the lesson as a new independent project.
