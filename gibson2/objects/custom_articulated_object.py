from gibson2.objects.articulated_object import ArticulatedObject
from gibson2.utils.custom_utils import create_uniform_ori_sampler, create_uniform_pos_sampler

class CustomArticulatedObject(ArticulatedObject):
    """
    A custom class that extends the articulated object by assigning this object a name, keeping track of its class id,
    and providing sampling functions for automatically sampling positions / orientations for this object

    Args:
        name (str): Name to assign this object -- should be unique

        filename (str): fpath to the urdf associated with this object

        scale (float): relative scale of the object when loading

        class_id (int): integer to assign to this object when using semantic segmentation

        pos_range (None or 2-tuple of 3-array): [min, max] values to uniformly sample position from, where min, max are
            each composed of a (x, y, z) array. If None, `'pos_sampler'` must be specified.

        rot_range (None or 2-array): [min, max] rotation to uniformly sample from.
            If None, `'ori_sampler'` must be specified.

        rot_axis (None or str): One of {`'x'`, `'y'`, `'z'`}, the axis to sample rotation from.
            If None, `'ori_sampler'` must be specified.

        pos_sampler (None or function): function that should take no args and return a 3-tuple for the
            global (x,y,z) cartesian position values for the object. Overrides `'pos_range'` if both are specified.
            If None, `'pos_range'` must be specified.

        ori_sampler (None or function): function that should take no args and return a 4-tuple for the
            global (x,y,z,w) quaternion for the object. Overrides `'rot_range'` and `'rot_axis'` if all are specified.
            If None, `'rot_range'` and `'rot_axis'` must be specified.
    """
    def __init__(
        self,
        name,
        class_id,
        pos_range,
        rot_range,
        rot_axis,
        pos_sampler,
        ori_sampler,
        filename,
        scale=1,
    ):
        # Run super init first
        super().__init__(filename=filename, scale=scale)

        # Store other internal vars
        self.name = name
        self.class_id = class_id

        # Compose samplers
        if pos_sampler is None:
            assert pos_range is not None, "Either pos_sampler or pos_range must be specified!"
            pos_sampler = create_uniform_pos_sampler(low=pos_range[0], high=pos_range[1])
        if ori_sampler is None:
            assert rot_range is not None and rot_axis is not None,\
                "Either ori_sampler or rot_range and rot_axis must be specified!"
            ori_sampler = create_uniform_ori_sampler(low=rot_range[0], high=rot_range[1], axis=rot_axis)

        self.pos_sampler = pos_sampler
        self.ori_sampler = ori_sampler

    def sample_pose(self):
        """
        Samples a new pose for this object.

        Returns:
            2-tuple:
                3-array: (x,y,z) cartesian global pos for this object
                4-array: (x,y,z,w) quaternion global orientation for this object
        """
        assert self.pos_sampler is not None and self.ori_sampler is not None, "Samplers still need to be added!"
        return self.pos_sampler(), self.ori_sampler()

    def update_pos_sampler(self, pos_sampler):
        """
        Updates the internal position sampler

        Args:
            pos_sampler (function): function that should take no args and return a 3-tuple for the
                global (x,y,z) cartesian position values for the object.
        """
        self.pos_sampler = pos_sampler

    def update_ori_sampler(self, ori_sampler):
        """
        Updates the internal orientation sampler

        Args:
            ori_sampler (None or function): function that should take no args and return a 4-tuple for the
                global (x,y,z,w) quaternion for the object.
        """
        self.ori_sampler = ori_sampler