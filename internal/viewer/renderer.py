from typing import Literal
import torch.nn.functional
import internal.renderers as renderers
import matplotlib


class ViewerRenderer:
    def __init__(
            self,
            gaussian_model,
            renderer: renderers.Renderer,
            background_color,
    ):
        super().__init__()

        self.gaussian_model = gaussian_model
        self.renderer = renderer
        self.background_color = background_color

        self.render_type = "rgb"
        self.output_key = "render"

        self.output_processor = self.no_processing

    def _setup_depth_map_options(self, viewer, server):
        self.max_depth_gui_number = server.gui.add_number(
            label="Max Clamp",
            initial_value=0.,
            min=0.,
            step=0.01,
            hint="value=0 means that no max clamping, value will be normalized based on the maximum one",
            visible=False,
        )
        self.depth_map_color_map_dropdown = server.gui.add_dropdown(
            label="Color Map",
            options=["turbo", "viridis", "magma", "inferno", "cividis", "gray"],
            initial_value="turbo",
            visible=False,
        )

        @self.max_depth_gui_number.on_update
        @self.depth_map_color_map_dropdown.on_update
        def _(event):
            with server.atomic():
                viewer.rerender_for_all_client()

    def _set_depth_map_option_visibility(self, visible: bool):
        self.max_depth_gui_number.visible = visible
        self.depth_map_color_map_dropdown.visible = visible

    def _set_output_type(self, name: str, key: str):
        """
        Update properties
        """
        # toggle depth map option
        self._set_depth_map_option_visibility(False)

        if self.renderer.is_type_depth_map(name) is True:
            self.output_processor = self.depth_map_processor
            self._set_depth_map_option_visibility(True)
        elif self.renderer.is_type_normal_map(name) is True:
            self.output_processor = self.normal_map_processor
        else:
            self.output_processor = self.no_processing
        # update key
        self.render_type = name
        self.output_key = key

    def setup_options(self, viewer, server):
        with server.gui.add_folder("Output"):
            available_output_types = self.renderer.get_available_output_types()
            first_type_name = list(available_output_types.keys())[0]
            first_type_key = available_output_types[first_type_name]

            # setup output type dropdown
            output_type_dropdown = server.gui.add_dropdown(
                label="Type",
                options=list(available_output_types.keys()),
                initial_value=first_type_name,
            )
            self.output_type_dropdown = output_type_dropdown

            @output_type_dropdown.on_update
            def _(event):
                if event.client is None:
                    return
                with server.atomic():
                    # whether valid type
                    new_key = available_output_types.get(output_type_dropdown.value, None)
                    if new_key is None:
                        return

                    self._set_output_type(output_type_dropdown.value, new_key)

                    viewer.rerender_for_all_client()

            self._setup_depth_map_options(viewer, server)

        # update default output type to the first one
        self._set_output_type(name=first_type_name, key=first_type_key)

    def get_outputs(self, camera, scaling_modifier: float = 1.):
        image = self.renderer(
            camera,
            self.gaussian_model,
            self.background_color,
            scaling_modifier=scaling_modifier,
            render_types=[self.render_type],
        )[self.output_key]
        image = self.output_processor(image)
        if image.shape[0] == 1:
            image = image.repeat(3, 1, 1)
        return image

    def depth_map_processor(self, depth_map):
        # TODO: the pixels not covered by any Gaussian (alpha==0), should be 1. after normalization
        max_depth = self.max_depth_gui_number.value
        if max_depth == 0:
            max_depth = depth_map.max()
        depth_map = (depth_map / (max_depth + 1e-8)).clamp(max=1.)
        return self.apply_float_colormap(depth_map, self.depth_map_color_map_dropdown.value)

    def normal_map_processor(self, normal_map):
        return torch.nn.functional.normalize(normal_map, dim=0) * 0.5 + 0.5

    def no_processing(self, i):
        return i

    @staticmethod
    def apply_float_colormap(image, colormap: Literal["default", "turbo", "viridis", "magma", "inferno", "cividis", "gray"]):
        """Copied from NeRFStudio

        Convert single channel to a color image.

        Args:
            image: Single channel image.
            colormap: Colormap for image.

        Returns:
            Tensor: Colored image with colors in [0, 1]
        """
        if colormap == "default":
            colormap = "turbo"

        image = torch.nan_to_num(image, 0)
        if colormap == "gray":
            return image.repeat(3, 1, 1)
        image_long = (image * 255).long()
        image_long_min = torch.min(image_long)
        image_long_max = torch.max(image_long)
        assert image_long_min >= 0, f"the min value is {image_long_min}"
        assert image_long_max <= 255, f"the max value is {image_long_max}"
        return torch.tensor(matplotlib.colormaps[colormap].colors, device=image.device)[image_long[0, ...]].permute(2, 0, 1)
