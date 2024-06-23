from abc import ABCMeta, abstractmethod
from amaranth import *
from amaranth.lib import io
import argparse

from ..gateware.pads import Pads


__all__  = ["AccessArguments"]
__all__ += ["AccessMultiplexer", "AccessMultiplexerInterface"]
__all__ += ["AccessDemultiplexer", "AccessDemultiplexerInterface"]


class AccessArguments(metaclass=ABCMeta):
    def _arg_error(self, message):
        raise argparse.ArgumentTypeError(f"applet {self._applet_name!r}: " + message)

    @abstractmethod
    def add_build_arguments(self, parser):
        pass

    @abstractmethod
    def add_run_arguments(self, parser):
        pass

    @abstractmethod
    def add_pin_argument(self, parser, name, default=None, required=False):
        pass

    @abstractmethod
    def add_pin_set_argument(self, parser, name, width, default=None, required=False):
        pass


class AccessMultiplexer(Elaboratable, metaclass=ABCMeta):
    @abstractmethod
    def set_analyzer(self, analyzer):
        pass

    @abstractmethod
    def claim_interface(self, applet, args, with_analyzer=True):
        pass


class AccessMultiplexerInterface(Elaboratable, metaclass=ABCMeta):
    def __init__(self, applet, analyzer):
        self.applet   = applet
        self.logger   = applet.logger
        self.analyzer = analyzer
        self.pads     = None

    @abstractmethod
    def get_out_fifo(self, **kwargs):
        pass

    @abstractmethod
    def get_in_fifo(self, **kwargs):
        pass

    def get_inout_fifo(self, **kwargs):
        return (self.get_in_fifo(**kwargs), self.get_out_fifo(**kwargs))

    @abstractmethod
    def build_pin_tristate(self, pin, oe, o, i):
        pass

    @abstractmethod
    def get_pin_name(self, pin):
        pass

    def get_pins(self, pins, name=None):
        triple = io.Buffer.Signature("io", len(pins)).create()
        for n, pin in enumerate(pins):
            self.build_pin_tristate(pin, triple.oe, triple.o[n], triple.i[n])

        if name is None:
            name = "-".join([self.get_pin_name(pins) for pins in pins])
        if self.analyzer:
            self.analyzer.add_pin_event(self.applet, name, triple)

        return triple

    def get_pin(self, pin, name=None):
        return self.get_pins([pin], name)

    def get_pads(self, args, pins=[], pin_sets=[]):
        pad_args = {}

        for pin in pins:
            pin_num = getattr(args, f"pin_{pin}")
            if pin_num is None:
                self.logger.debug("not assigning pin %r to any device pin", pin)
            else:
                self.logger.debug("assigning pin %r to device pin %s",
                    pin, self.get_pin_name(pin_num))
                pad_args[pin] = self.get_pin(pin_num, name=pin)

        for pin_set in pin_sets:
            pin_nums = getattr(args, f"pin_set_{pin_set}")
            if pin_nums is None:
                self.logger.debug("not assigning pin set %r to any device pins", pin_set)
            else:
                self.logger.debug("assigning pin set %r to device pins %s",
                    pin_set, ", ".join([self.get_pin_name(pin_num) for pin_num in pin_nums]))
                pad_args[pin_set] = self.get_pins(pin_nums, name=pin_set)

        self.pads = Pads(**pad_args)
        return self.pads


class AccessDemultiplexer(metaclass=ABCMeta):
    def __init__(self, device):
        self.device = device
        self._interfaces = []

    @abstractmethod
    async def claim_interface(self, applet, mux_interface, args, timeout=None):
        pass

    async def flush(self):
        for iface in self._interfaces:
            await iface.flush()

    async def cancel(self):
        for iface in self._interfaces:
            await iface.cancel()

    def statistics(self):
        for iface in self._interfaces:
            iface.statistics()


class AccessDemultiplexerInterface(metaclass=ABCMeta):
    def __init__(self, device, applet):
        self.device = device
        self.applet = applet
        self.logger = applet.logger

    @abstractmethod
    async def cancel(self):
        pass

    @abstractmethod
    async def reset(self):
        pass

    @abstractmethod
    async def read(self, length=None, *, flush=True):
        pass

    @abstractmethod
    async def write(self, data):
        pass

    @abstractmethod
    async def flush(self, wait=True):
        pass

    def statistics(self):
        pass
