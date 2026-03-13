import pygame
from ..math import Float2, Float3

pygame.joystick.init()
JOYSTICKS = [pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())]

class InputManager:

    """ JOYPAD INPUT CONSTANTS """
    # Joypad buttons
    J_A = 0
    J_B = 1
    J_X = 2
    J_Y = 3
    J_LB = 4
    J_RB = 5
    J_BACK = 6
    J_START = 7
    J_LEFT_STICK = 8
    J_RIGHT_STICK = 9
    # D-pad hats
    J_HAT_X = 0  
    J_HAT_Y = 1
    J_HAT_L = 2
    J_HAT_R = 3
    J_HAT_U = 4
    J_HAT_D = 5
    # Axes
    J_LEFT_X = 0
    J_LEFT_Y = 1
    J_RIGHT_X = 2
    J_RIGHT_Y = 3
    J_LT = 4
    J_RT = 5

    """ MOUSE INPUT CONSTANTS """
    # Mouse buttons
    M_LEFT = 1
    M_MIDDLE = 2
    M_RIGHT = 3
    M_BTN4 = None # NOT SUPPORTED YET
    M_BTN5 = None # NOT SUPPORTED YET
    # Mouse wheel
    M_WHEEL_X = None # NOT SUPPORTED YET
    M_WHEEL_Y = None # NOT SUPPORTED YET
    # Mouse motion
    M_MOTION_X = 0
    M_MOTION_Y = 1

    # Mapping input types
    KEY = 'key'
    JOY_BUTTON = 'joy_button'
    __JOY_BUTTON_RANGE = (0, 9)
    JOY_AXIS = 'joy_axis'
    __JOY_AXIS_RANGE = (0, 5)
    JOY_HAT = 'joy_hat'
    __JOY_HAT_RANGE = (0, 5)
    MOUSE_BUTTON = 'mouse_button'
    __MOUSE_BUTTON_RANGE = (0, 2)
    MOUSE_MOTION = 'mouse_motion'
    __MOUSE_MOTION_RANGE = (0, 1)
    MOUSE_WHEEL = 'mouse_wheel'
    __MOUSE_WHEEL_RANGE = (0, 0)
    
    # Action value types
    ACTION_HELD = 'held'
    ACTION_DOWN = 'down'
    ACTION_UP = 'up'

    # Action value options
    OPTION_CONTROLLER = 'controller'

    # Normalize Options
    NORM_NONE = 0
    NORM_REGULAR = 1
    # NORM_MAX_SCALE = 2



    __input_mappings = {
        # 'move': {
        #     'disabled': False,
        #     'normalized': True,
        #     'base_value': Float3(0, 0, 0),
        #     'keys': [(pygame.K_w, KEY, Float3(0, 0, 1)), (pygame.K_s, KEY, Float3(0, 0, -1)),
        #              (pygame.K_a, KEY, Float3(-1, 0, 0)), (pygame.K_d, KEY, Float3(1, 0, 0)),
        #              (pygame.K_SPACE, KEY, Float3(0, 1, 0)), (pygame.K_LSHIFT, KEY, Float3(0, -1, 0))]
        # },
        # 'test': {
        #     'normalized': True,
        #     'base_value': Float2(0, 0),
        #     'keys': [(J_LEFT_X, JOY_AXIS, Float2(1, 0), 0), (J_LEFT_Y, JOY_AXIS, Float2(0, 1), 0)]
        # }
    }
    
    __action_pulses_up = []
    __action_pulses_down = []
    __action_values = []
    
    __mouse_frame_rel = None
    __mouse_wheel_frame_rel = None

    """ Window focus and cursor states """
    __window_focused = True
    __prevent_input = False
    __lock_cursor = True
    __hide_cursor = True
    
    def print_mappings():
        print(InputManager.__input_mappings)

    def process_events(events):
        global JOYSTICKS
        InputManager.__mouse_frame_rel = pygame.mouse.get_rel()
        
        # print(InputManager.__action_pulses_down)
        # if (len(InputManager.__action_values) > 0):
        #     print(InputManager.__action_values)

        InputManager.__action_pulses_down = []
        InputManager.__action_pulses_up = []
        
        for event in events:
            if event.type == pygame.JOYAXISMOTION:
                pass
            if event.type == pygame.JOYHATMOTION:
                """ Joy hat x axis handling """
                if event.value[0] == 1:
                    InputManager.__action_pulses_down.append((InputManager.J_HAT_R, InputManager.JOY_HAT))
                    InputManager.__action_values.append((InputManager.J_HAT_R, InputManager.JOY_HAT))
                elif (InputManager.J_HAT_R, InputManager.JOY_HAT) in InputManager.__action_values:
                    InputManager.__action_pulses_up.append((InputManager.J_HAT_R, InputManager.JOY_HAT))
                    InputManager.__action_values.remove((InputManager.J_HAT_R, InputManager.JOY_HAT))
                    
                if event.value[0] == -1:
                    InputManager.__action_pulses_down.append((InputManager.J_HAT_L, InputManager.JOY_HAT))
                    InputManager.__action_values.append((InputManager.J_HAT_L, InputManager.JOY_HAT))
                elif (InputManager.J_HAT_L, InputManager.JOY_HAT) in InputManager.__action_values:
                    InputManager.__action_pulses_up.append((InputManager.J_HAT_L, InputManager.JOY_HAT))
                    InputManager.__action_values.remove((InputManager.J_HAT_L, InputManager.JOY_HAT))

                if event.value[0] != 0 and (InputManager.J_HAT_X, InputManager.JOY_HAT) not in InputManager.__action_values:
                    InputManager.__action_pulses_down.append((InputManager.J_HAT_X, InputManager.JOY_HAT))
                    InputManager.__action_values.append((InputManager.J_HAT_X, InputManager.JOY_HAT))
                elif event.value[0] == 0 and (InputManager.J_HAT_X, InputManager.JOY_HAT) in InputManager.__action_values:
                    InputManager.__action_pulses_up.append((InputManager.J_HAT_X, InputManager.JOY_HAT))
                    InputManager.__action_values.remove((InputManager.J_HAT_X, InputManager.JOY_HAT))
                    
                """ Joy hat y axis handling """
                if event.value[1] == 1:
                    InputManager.__action_pulses_down.append((InputManager.J_HAT_U, InputManager.JOY_HAT))
                    InputManager.__action_values.append((InputManager.J_HAT_U, InputManager.JOY_HAT))
                elif (InputManager.J_HAT_U, InputManager.JOY_HAT) in InputManager.__action_values:
                    InputManager.__action_pulses_up.append((InputManager.J_HAT_U, InputManager.JOY_HAT))
                    InputManager.__action_values.remove((InputManager.J_HAT_U, InputManager.JOY_HAT))

                if event.value[1] == -1:
                    InputManager.__action_pulses_down.append((InputManager.J_HAT_D, InputManager.JOY_HAT))
                    InputManager.__action_values.append((InputManager.J_HAT_D, InputManager.JOY_HAT))
                elif (InputManager.J_HAT_D, InputManager.JOY_HAT) in InputManager.__action_values:
                    InputManager.__action_pulses_up.append((InputManager.J_HAT_D, InputManager.JOY_HAT))
                    InputManager.__action_values.remove((InputManager.J_HAT_D, InputManager.JOY_HAT))

                if event.value[1] != 0 and (InputManager.J_HAT_Y, InputManager.JOY_HAT) not in InputManager.__action_values:
                    InputManager.__action_pulses_down.append((InputManager.J_HAT_Y, InputManager.JOY_HAT))
                    InputManager.__action_values.append((InputManager.J_HAT_Y, InputManager.JOY_HAT))
                elif event.value[1] == 0 and (InputManager.J_HAT_Y, InputManager.JOY_HAT) in InputManager.__action_values:
                    InputManager.__action_pulses_up.append((InputManager.J_HAT_Y, InputManager.JOY_HAT))
                    InputManager.__action_values.remove((InputManager.J_HAT_Y, InputManager.JOY_HAT))


            if event.type == pygame.JOYBUTTONDOWN:
                InputManager.__action_pulses_down.append((event.button, InputManager.JOY_BUTTON))
                InputManager.__action_values.append((event.button, InputManager.JOY_BUTTON))
                
            if event.type == pygame.JOYBUTTONUP:
                InputManager.__action_pulses_up.append((event.button, InputManager.JOY_BUTTON))
                InputManager.__action_values.remove((event.button, InputManager.JOY_BUTTON))
                
            if event.type == pygame.JOYBALLMOTION:
                # I dont have any idea what this is...
                pass
            
            if event.type == pygame.JOYDEVICEADDED:
                JOYSTICKS = [pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())]
                for j in JOYSTICKS:
                    j.init()
            if event.type == pygame.JOYDEVICEREMOVED:
                JOYSTICKS = [pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())]
                for j in JOYSTICKS:
                    j.init()
                    
            if event.type == pygame.MOUSEWHEEL:
                InputManager.__mouse_wheel_frame_rel = (event.x, event.y)
            if event.type == pygame.MOUSEBUTTONDOWN:
                if (event.button == 4 or event.button == 5):  # Ignore wheel events here
                    continue
                InputManager.__action_pulses_down.append((event.button, InputManager.MOUSE_BUTTON))
                InputManager.__action_values.append((event.button, InputManager.MOUSE_BUTTON))
            if event.type == pygame.MOUSEBUTTONUP:
                if (event.button == 4 or event.button == 5):  # Ignore wheel events here
                    continue
                InputManager.__action_pulses_up.append((event.button, InputManager.MOUSE_BUTTON))
                InputManager.__action_values.remove((event.button, InputManager.MOUSE_BUTTON))
                
            if event.type == pygame.KEYDOWN:
                InputManager.__action_pulses_down.append((event.key, InputManager.KEY))
                InputManager.__action_values.append((event.key, InputManager.KEY))
                
            if event.type == pygame.KEYUP:
                InputManager.__action_pulses_up.append((event.key, InputManager.KEY))
                InputManager.__action_values.remove((event.key, InputManager.KEY))

            if event.type == pygame.WINDOWFOCUSGAINED:
                pygame.event.set_grab(InputManager.__lock_cursor)
                pygame.mouse.set_visible(not InputManager.__hide_cursor)
                InputManager.__window_focused = True
                if (InputManager.__prevent_input):
                    InputManager.__prevent_input = False
            if event.type == pygame.WINDOWFOCUSLOST:
                pygame.event.set_grab(False)
                pygame.mouse.set_visible(True)
                InputManager.__window_focused = False
            if event.type == pygame.MOUSEBUTTONDOWN and InputManager.__prevent_input:
                pygame.event.set_grab(InputManager.__lock_cursor)
                pygame.mouse.set_visible(not InputManager.__hide_cursor)
                InputManager.__prevent_input = False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE and not InputManager.__prevent_input:
                pygame.event.set_grab(False)
                pygame.mouse.set_visible(True)
                InputManager.__prevent_input = True
                

    def clear_mappings():
        InputManager.__input_mappings = {}

    def clear_mapping(action_name):
        if action_name in InputManager.__input_mappings:
            del InputManager.__input_mappings[action_name]

    def clear_mapping_actions(mapping_name):
        if mapping_name in InputManager.__input_mappings:
            InputManager.__input_mappings[mapping_name]['keys'] = []
        
    def clear_mapping_action(mapping_name, key, input_type):
        if mapping_name in InputManager.__input_mappings:
            mapping = InputManager.__input_mappings[mapping_name]
            # Basically filter out the matching key/input_type pair (Don't care about value or options here)
            mapping['keys'] = [action_data for action_data in mapping['keys'] if not (action_data[0] == key and action_data[1] == input_type)]

    def disable_mappings(action_names):
        if not isinstance(action_names, list):
            action_names = [action_names]
        
        for action_name in action_names:
            if action_name in InputManager.__input_mappings:
                InputManager.__input_mappings[action_name]['disabled'] = True

    def enable_mappings(action_names):
        if not isinstance(action_names, list):
            action_names = [action_names]

        for action_name in action_names:
            if action_name in InputManager.__input_mappings:
                InputManager.__input_mappings[action_name]['disabled'] = False

    def add_mapping(action_name, base_value, normalized=True):
        InputManager.__input_mappings[action_name] = { 'normalized': normalized, 'base_value': base_value, 'keys': [] }

    def add_mapping_input(action_name, key, input_type, value, options: dict = None):
        if action_name not in InputManager.__input_mappings:
            InputManager.add_mapping(action_name)

        mapping = InputManager.__input_mappings[action_name]

        for i, action_data in enumerate(mapping['keys']):
            action_key, action_type = action_data[0], action_data[1]
            if action_key == key and action_type == input_type:
                mapping['keys'][i] = (key, action_type, value, options) if options is not None else (key, action_type, value)
                return

        mapping['keys'].append((key, input_type, value, options) if options is not None else (key, input_type, value))

    def get_action_held(action_name):
        return InputManager.__get_action_value(action_name, InputManager.ACTION_HELD)
    def get_action_down(action_name):
        return InputManager.__get_action_value(action_name, InputManager.ACTION_DOWN)
    def get_action_up(action_name):
        return InputManager.__get_action_value(action_name, InputManager.ACTION_UP)

    def __get_joystick(id: int = 0) -> pygame.joystick.JoystickType:
        if len(JOYSTICKS) > id:
            return JOYSTICKS[id]
        return None

    def __get_action_value(action_name, value_type=ACTION_HELD):
        if action_name not in InputManager.__input_mappings:
            return None

        mapping = InputManager.__input_mappings[action_name]    
        result = mapping['base_value']
        
        if (not InputManager.__window_focused) or InputManager.__prevent_input:
            return result
        
        if 'disabled' in mapping and mapping['disabled']:
            return result

        # Determine which value list to check against
        value_compare_list = InputManager.__action_values
        if value_type == InputManager.ACTION_UP:
            value_compare_list = InputManager.__action_pulses_up
        if value_type == InputManager.ACTION_DOWN:
            value_compare_list = InputManager.__action_pulses_down

        for action_data in mapping['keys']:
            key, input_type, value = action_data[0], action_data[1], action_data[2]
            options = {}
            if len(action_data) > 3:
                options = action_data[3]
                
            input_value = InputManager.__get_input_mapping_value(key, input_type, value, options, value_compare_list)
            if input_value is not None:
                result += input_value

        if mapping['normalized'] == InputManager.NORM_REGULAR:
            if isinstance(result, (Float2, Float3)):
                result = result.normalize()
            elif isinstance(result, (int, float)) and result != 0:
                result = result / abs(result) # Normalize to -1 or 1

        return result

    def __get_input_mapping_value(key, input_type, value, options: dict, value_compare_list):
        """ Key based values """
        if input_type == InputManager.KEY:
            if (key, input_type) not in value_compare_list:
                return None
            
            return value
        
        """ Joypad button based values """
        if input_type == InputManager.JOY_BUTTON:
            if not InputManager.__JOY_BUTTON_RANGE[0] <= key <= InputManager.__JOY_BUTTON_RANGE[1]:
                return None

            if (key, input_type) not in value_compare_list:
                return None
            
            return value
        
        """ Joypad axis based values """
        if input_type == InputManager.JOY_AXIS:
            if not InputManager.__JOY_AXIS_RANGE[0] <= key <= InputManager.__JOY_AXIS_RANGE[1]:
                return None

            controller_number = options.get(InputManager.OPTION_CONTROLLER, 0)
            joystick: pygame.joystick.JoystickType = InputManager.__get_joystick(controller_number)
            if joystick is None:
                return None

            axis_value = joystick.get_axis(key)
            if abs(axis_value) > 0.1:  # Deadzone
                return value * axis_value
            
        """ Joypad hat based values """
        if input_type == InputManager.JOY_HAT:
            if not InputManager.__JOY_HAT_RANGE[0] <= key <= InputManager.__JOY_HAT_RANGE[1]:
                return None
            
            if (key, input_type) not in value_compare_list:
                return None
            
            controller_number = options.get(InputManager.OPTION_CONTROLLER, 0)
            joystick: pygame.joystick.JoystickType = InputManager.__get_joystick(controller_number)
            if joystick is None:
                return None
            
            if (key == InputManager.J_HAT_X) or (key == InputManager.J_HAT_Y):
                hat_value = joystick.get_hat(0)[key]  # Assuming single hat
                return value * hat_value

            hat_value = joystick.get_hat(0)
            if (key == InputManager.J_HAT_L):
                return value if hat_value[0] == -1 else 0

            if (key == InputManager.J_HAT_R):
                return value if hat_value[0] == 1 else 0

            if (key == InputManager.J_HAT_U):
                return value if hat_value[1] == 1 else 0

            if (key == InputManager.J_HAT_D):   
                return value if hat_value[1] == -1 else 0

        """ Mouse button based values """
        if input_type == InputManager.MOUSE_BUTTON:
            if not InputManager.__MOUSE_BUTTON_RANGE[0] <= key <= InputManager.__MOUSE_BUTTON_RANGE[1]:
                return None
            
            if (key, input_type) not in value_compare_list:
                return None
            
            return value
            
        """ Mouse wheel based values """
        if input_type == InputManager.MOUSE_WHEEL:
            if not InputManager.__MOUSE_WHEEL_RANGE[0] <= key <= InputManager.__MOUSE_WHEEL_RANGE[1]:
                return None
            
            if InputManager.__mouse_wheel_frame_rel is None:
                return None
            
            wheel_rel = InputManager.__mouse_wheel_frame_rel
            return value * wheel_rel[key]
        
        """ Mouse motion based values """
        if input_type == InputManager.MOUSE_MOTION:
            if not InputManager.__MOUSE_MOTION_RANGE[0] <= key <= InputManager.__MOUSE_MOTION_RANGE[1]:
                return None

            rel = InputManager.__mouse_frame_rel
            return value * rel[key]
        return None