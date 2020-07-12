import numpy as np

from matplotlib.backends.backend_agg import RendererAgg
from matplotlib.tight_bbox import process_figure_for_rasterizing


class MixedModeRenderer:
    """
    A helper class to implement a renderer that switches between
    vector and raster drawing.  An example may be a PDF writer, where
    most things are drawn with PDF vector commands, but some very
    complex objects, such as quad meshes, are rasterised and then
    output as images.
    """
    def __init__(self, figure, width, height, dpi, vector_renderer,
                 raster_renderer_class=None,
                 bbox_inches_restore=None):
        """
        Parameters
        ----------
        figure : `matplotlib.figure.Figure`
            The figure instance.
        width : scalar
            The width of the canvas in logical units
        height : scalar
            The height of the canvas in logical units
        dpi : float
            The dpi of the canvas
        vector_renderer : `matplotlib.backend_bases.RendererBase`
            An instance of a subclass of
            `~matplotlib.backend_bases.RendererBase` that will be used for the
            vector drawing.
        raster_renderer_class : `matplotlib.backend_bases.RendererBase`
            The renderer class to use for the raster drawing.  If not provided,
            this will use the Agg backend (which is currently the only viable
            option anyway.)

        """
        if raster_renderer_class is None:
            raster_renderer_class = RendererAgg

        self._raster_renderer_class = raster_renderer_class
        self._width = width
        self._height = height
        self.dpi = dpi

        self._vector_renderer = vector_renderer

        self._raster_renderer = None
        self._rasterizing = 0

        # A reference to the figure is needed as we need to change
        # the figure dpi before and after the rasterization. Although
        # this looks ugly, I couldn't find a better solution. -JJL
        self.figure = figure
        self._figdpi = figure.get_dpi()

        self._bbox_inches_restore = bbox_inches_restore

        self._renderer = vector_renderer

    def __getattr__(self, attr):
        # Proxy everything that hasn't been overridden to the base
        # renderer. Things that *are* overridden can call methods
        # on self._renderer directly, but must not cache/store
        # methods (because things like RendererAgg change their
        # methods on the fly in order to optimise proxying down
        # to the underlying C implementation).
        return getattr(self._renderer, attr)

    def start_rasterizing(self):
        """
        Enter "raster" mode.  All subsequent drawing commands (until
        `stop_rasterizing` is called) will be drawn with the raster backend.
        """
        # change the dpi of the figure temporarily.
        self.figure.set_dpi(self.dpi)
        if self._bbox_inches_restore:  # when tight bbox is used
            r = process_figure_for_rasterizing(self.figure,
                                               self._bbox_inches_restore)
            self._bbox_inches_restore = r
        if self._rasterizing == 0:
            self._raster_renderer = self._raster_renderer_class(
                self._width*self.dpi, self._height*self.dpi, self.dpi)
            self._renderer = self._raster_renderer
        self._rasterizing += 1

    def stop_rasterizing(self):
        """
        Exit "raster" mode.  All of the drawing that was done since
        the last `start_rasterizing` call will be copied to the
        vector backend by calling draw_image.

        If `start_rasterizing` has been called multiple times,
        `stop_rasterizing` must be called the same number of times before
        "raster" mode is exited.
        """
        self._rasterizing -= 1
        if self._rasterizing == 0:
            self._renderer = self._vector_renderer

            height = self._height * self.dpi
            buffer, bounds = self._raster_renderer.tostring_rgba_minimized()
            l, b, w, h = bounds
            if w > 0 and h > 0:
                image = np.frombuffer(buffer, dtype=np.uint8)
                image = image.reshape((h, w, 4))
                image = image[::-1]
                gc = self._renderer.new_gc()
                # TODO: If the mixedmode resolution differs from the figure's
                #       dpi, the image must be scaled (dpi->_figdpi). Not all
                #       backends support this.
                self._renderer.draw_image(
                    gc,
                    l * self._figdpi / self.dpi,
                    (height-b-h) * self._figdpi / self.dpi,
                    image)
            self._raster_renderer = None
            self._rasterizing = False

            # restore the figure dpi.
            self.figure.set_dpi(self._figdpi)

        if self._bbox_inches_restore:  # when tight bbox is used
            r = process_figure_for_rasterizing(self.figure,
                                               self._bbox_inches_restore,
                                               self._figdpi)
            self._bbox_inches_restore = r
