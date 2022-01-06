"""
Example script demo'ing robot control.

Options for random actions, as well as selection of robot action space
"""
import logging
import random
from collections import OrderedDict

import cv2
import numpy as np
import pybullet as p

from igibson.render.mesh_renderer.mesh_renderer_settings import MeshRendererSettings
from igibson.robots import REGISTERED_ROBOTS
from igibson.scenes.empty_scene import EmptyScene
from igibson.scenes.igibson_indoor_scene import InteractiveIndoorScene
from igibson.simulator import Simulator

CONTROL_MODES = OrderedDict(
    random="Use autonomous random actions (default)",
    teleop="Use keyboard control",
)

SCENES = OrderedDict(
    Rs_int="Realistic interactive home environment (default)",
    empty="Empty environment with no objects",
)

GUIS = OrderedDict(
    ig="iGibson GUI (default)",
    pb="PyBullet GUI",
    all="Use both IG and PB GUI",
)

ARROWS = {
    0: "up_arrow",
    1: "down_arrow",
    2: "left_arrow",
    3: "right_arrow",
    65295: "left_arrow",
    65296: "right_arrow",
    65297: "up_arrow",
    65298: "down_arrow",
}


def choose_from_options(options, name, random_selection=False):
    """
    Prints out options from a list, and returns the requested option.

    :param options: dict or Array, options to choose from. If dict, the value entries are assumed to be docstrings
        explaining the individual options
    :param name: str, name of the options
    :param random_selection: bool, if the selection is random (for automatic demo execution). Default False

    :return str: Requested option
    """
    # Select robot
    print("\nHere is a list of available {}s:\n".format(name))

    for k, option in enumerate(options):
        docstring = ": {}".format(options[option]) if isinstance(options, dict) else ""
        print("[{}] {}{}".format(k + 1, option, docstring))
    print()

    if not random_selection:
        try:
            s = input("Choose a {} (enter a number from 1 to {}): ".format(name, len(options)))
            # parse input into a number within range
            k = min(max(int(s), 1), len(options)) - 1
        except:
            k = 0
            print("Input is not valid. Use {} by default.".format(list(options)[k]))
    else:
        k = random.choice(range(len(options)))

    # Return requested option
    return list(options)[k]


def choose_controllers(robot, random_selection=False):
    """
    For a given robot, iterates over all components of the robot, and returns the requested controller type for each
    component.

    :param robot: BaseRobot, robot class from which to infer relevant valid controller options

    :return OrderedDict: Mapping from individual robot component (e.g.: base, arm, etc.) to selected controller names
    """
    # Create new dict to store responses from user
    controller_choices = OrderedDict()

    # Grab the default controller config so we have the registry of all possible controller options
    default_config = robot._default_controller_config

    # Iterate over all components in robot
    for component, controller_options in default_config.items():
        # Select controller
        options = list(sorted(controller_options.keys()))
        choice = choose_from_options(
            options=options, name="{} controller".format(component), random_selection=random_selection
        )

        # Add to user responses
        controller_choices[component] = choice

    return controller_choices


class KeyboardController:
    """
    Simple class for controlling iGibson robots using keyboard commands
    """

    def __init__(
        self,
        robot,
    ):
        """
        :param robot: BaseRobot, robot to control
        """
        # Store relevant info from robot
        self.action_dim = robot.action_dim
        self.controller_info = OrderedDict()
        idx = 0
        for name, controller in robot._controllers.items():
            self.controller_info[name] = {
                "name": type(controller).__name__,
                "start_idx": idx,
                "command_dim": controller.command_dim,
            }
            idx += controller.command_dim

        # Other persistent variables we need to keep track of
        self.joint_control_idx = None  # Indices of joints being directly controlled via joint control
        self.current_joint = -1  # Active joint being controlled for joint control
        self.gripper_direction = 1.0  # Flips between -1 and 1
        self.persistent_gripper_action = None  # Whether gripper actions should persist between commands
        self.keypress_mapping = None
        self.populate_keypress_mapping()

    def populate_keypress_mapping(self):
        """
        Populates the mapping @self.keypress_mapping, which maps keypresses to action info:

            keypress:
                idx: <int>
                val: <float>
        """
        self.keypress_mapping = {}
        self.joint_control_idx = set()

        # Add mapping for joint control directions (no index because these are inferred at runtime)
        self.keypress_mapping["]"] = {"idx": None, "val": 0.1}
        self.keypress_mapping["["] = {"idx": None, "val": -0.1}

        # Iterate over all controller info and populate mapping
        for component, info in self.controller_info.items():
            if info["name"] == "JointController":
                for i in range(info["command_dim"]):
                    ctrl_idx = info["start_idx"] + i
                    self.joint_control_idx.add(ctrl_idx)
            elif info["name"] == "DifferentialDriveController":
                self.keypress_mapping["up_arrow"] = {"idx": info["start_idx"] + 0, "val": 0.2}
                self.keypress_mapping["down_arrow"] = {"idx": info["start_idx"] + 0, "val": -0.2}
                self.keypress_mapping["right_arrow"] = {"idx": info["start_idx"] + 1, "val": 0.1}
                self.keypress_mapping["left_arrow"] = {"idx": info["start_idx"] + 1, "val": -0.1}
            elif info["name"] == "InverseKinematicsController":
                self.keypress_mapping["i"] = {"idx": info["start_idx"] + 0, "val": 0.5}
                self.keypress_mapping["k"] = {"idx": info["start_idx"] + 0, "val": -0.5}
                self.keypress_mapping["j"] = {"idx": info["start_idx"] + 1, "val": 0.5}
                self.keypress_mapping["l"] = {"idx": info["start_idx"] + 1, "val": -0.5}
                self.keypress_mapping["p"] = {"idx": info["start_idx"] + 2, "val": 0.5}
                self.keypress_mapping[";"] = {"idx": info["start_idx"] + 2, "val": -0.5}
                self.keypress_mapping["n"] = {"idx": info["start_idx"] + 3, "val": 0.5}
                self.keypress_mapping["b"] = {"idx": info["start_idx"] + 3, "val": -0.5}
                self.keypress_mapping["o"] = {"idx": info["start_idx"] + 4, "val": 0.5}
                self.keypress_mapping["u"] = {"idx": info["start_idx"] + 4, "val": -0.5}
                self.keypress_mapping["v"] = {"idx": info["start_idx"] + 5, "val": 0.5}
                self.keypress_mapping["c"] = {"idx": info["start_idx"] + 5, "val": -0.5}
            elif info["name"] == "ParallelJawGripperController":
                if info["command_dim"] > 1:
                    for i in range(info["command_dim"]):
                        ctrl_idx = info["start_idx"] + i
                        self.joint_control_idx.add(ctrl_idx)
                else:
                    self.keypress_mapping[" "] = {"idx": info["start_idx"], "val": 1.0}
                    self.persistent_gripper_action = 1.0
            else:
                raise ValueError("Unknown controller name received: {}".format(info["name"]))

    def get_random_action(self):
        """
        :return Array: Generated random action vector (normalized)
        """
        return np.random.uniform(-1, 1, self.action_dim)

    def get_teleop_action(self):
        """
        :return Array: Generated action vector based on received user inputs from the keyboard
        """
        action = np.zeros(self.action_dim)
        keypress = self.get_keyboard_input()

        if keypress is not None:
            # If the keypress is a number, this is a joint action -- we must update the active joint
            if keypress.isnumeric() and int(keypress) in self.joint_control_idx:
                self.current_joint = int(keypress)
            # Get idx to modify the corresponding value
            action_info = self.keypress_mapping.get(keypress, None)
            if action_info is not None:
                idx, val = action_info["idx"], action_info["val"]
                # If the keypress is a spacebar, this is a gripper action -- we must toggle its direction
                if keypress == " ":
                    val *= self.gripper_direction
                    if self.persistent_gripper_action is not None:
                        self.persistent_gripper_action = val
                    self.gripper_direction *= -1.0

                # If there is no index, then we assume that we are controlling a joint, so we directly set the idx
                if idx is None:
                    idx = self.current_joint

                # Set action
                action[idx] = val

        # Possibly set the persistent gripper action
        if self.persistent_gripper_action is not None:
            action[self.keypress_mapping[" "]["idx"]] = self.persistent_gripper_action

        # Return action
        return action

    @staticmethod
    def get_keyboard_input():
        """
        Checks for newly received user inputs and returns the first received input, if any
        :return None or str: User input in string form. Note that only the characters mentioned in
        @self.print_keyboard_teleop_info are explicitly supported
        """
        if gui == "pb":
            keypress = p.getKeyboardEvents()
            keypress = -1 if len(keypress.keys()) == 0 else list(keypress.keys())[0]
        else:
            # todo: optimize for ig gui? seems very slow otherwise
            keypress = cv2.waitKey(1)

        # Handle special case of arrow keys, which are mapped differently between pybullet and cv2
        keypress = ARROWS.get(keypress, keypress)

        # Handle general case where a key was actually pressed (int value >= 0)
        if isinstance(keypress, int):
            keypress = chr(keypress) if keypress > -1 else None

        return keypress

    @staticmethod
    def print_keyboard_teleop_info():
        """
        Prints out relevant information for teleop controlling a robot
        """

        def print_command(char, info):
            char += " " * (10 - len(char))
            print("{}\t{}".format(char, info))

        print()
        print("*" * 30)
        print("Controlling the Robot Using the Keyboard")
        print("*" * 30)
        print()
        print("Joint Control")
        print_command("0-9", "specify the joint to control")
        print_command("[, ]", "move the joint backwards, forwards, respectively")
        print()
        print("Differential Drive Control")
        print_command(u"\u2190, \u2192", "turn left, right")
        print_command(u"\u2191, \u2193", "move forward, backwards")
        print()
        print("Inverse Kinematics Control")
        print_command("i, k", "translate arm along x-axis")
        print_command("l, j", "translate arm along y-axis")
        print_command("p, ;", "translate arm along z-axis")
        print_command("n, b", "rotate arm about x-axis")
        print_command("o, u", "rotate arm about y-axis")
        print_command("v, c", "rotate arm about z-axis")
        print()
        print("Boolean Gripper Control")
        print_command("spacebar", "toggle gripper (open/close)")
        print()
        print("*" * 30)
        print()


def main(random_selection=False):
    """
    Robot control demo with selection
    Queries the user to select a robot, the controllers, a scene and a type of input (random actions or teleop)
    """
    logging.info("*" * 80 + "\nDescription:" + main.__doc__ + "*" * 80)
    # Set rendering options
    rendering_settings = MeshRendererSettings(
        optimized=True,
        fullscreen=False,
        enable_shadow=True,
        enable_pbr=True,
        msaa=True,
        light_dimming_factor=1.0,
    )

    # Create an initial headless dummy scene so we can load the requested robot and extract useful info
    s = Simulator(mode="headless", use_pb_gui=False)
    scene = EmptyScene()
    s.import_scene(scene)

    # Get robot to create
    robot_name = choose_from_options(
        options=list(sorted(REGISTERED_ROBOTS.keys())), name="robot", random_selection=random_selection
    )
    robot = REGISTERED_ROBOTS[robot_name](action_type="continuous")
    s.import_robot(robot)

    # Get controller choice
    controller_choices = choose_controllers(robot=robot, random_selection=random_selection)

    # Choose control mode
    if random_selection:
        control_mode = "random"
    else:
        control_mode = choose_from_options(options=CONTROL_MODES, name="control mode")

    # Choose scene to load
    scene_id = choose_from_options(options=SCENES, name="scene", random_selection=random_selection)

    # Choose GUI
    gui = choose_from_options(options=GUIS, name="gui", random_selection=random_selection)

    # Infer what GUI(s) to use
    render_mode, use_pb_gui = None, None
    if gui == "ig":
        render_mode, use_pb_gui = "gui_interactive", False
    if gui == "pb":
        render_mode, use_pb_gui = "headless", True
    else:  # Use both
        render_mode, use_pb_gui = "gui_interactive", True

    # Shut down dummy simulator and re-create actual simulator
    s.disconnect()
    del s
    s = Simulator(mode=render_mode, use_pb_gui=use_pb_gui, image_width=512, image_height=512)

    # Load scene
    scene = (
        EmptyScene(render_floor_plane=True, floor_plane_rgba=[0.6, 0.6, 0.6, 1])
        if scene_id == "empty"
        else InteractiveIndoorScene(scene_id)
    )
    s.import_scene(scene)

    # Load robot
    robot = REGISTERED_ROBOTS[robot_name](
        action_type="continuous",
        action_normalize=True,
        controller_config={
            component: {"name": controller_name} for component, controller_name in controller_choices.items()
        },
    )
    s.import_robot(robot)

    # Reset the robot
    robot.set_position([0, 0, 0])
    robot.reset()
    robot.keep_still()

    # Set initial viewer if using IG GUI
    if gui != "pb":
        s.viewer.initial_pos = [1.6, 0, 1.3]
        s.viewer.initial_view_direction = [-0.7, 0, -0.7]
        s.viewer.reset_viewer()

    # Create teleop controller
    action_generator = KeyboardController(robot=robot)

    # Print out relevant keyboard info if using keyboard teleop
    if control_mode == "teleop":
        action_generator.print_keyboard_teleop_info()

    # Other helpful user info
    quit_cmd = "ctrl-q" if gui == "pb" else "ESC"
    print("Running demo. Switch to the viewer windows")
    print("Press {} to quit".format(quit_cmd))

    # Loop control until user quits
    while True:
        action = (
            action_generator.get_random_action() if control_mode == "random" else action_generator.get_teleop_action()
        )
        robot.apply_action(action)
        for _ in range(10):
            s.step()

    s.disconnect()


if __name__ == "__main__":
    main()
