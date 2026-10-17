"""USB discovery using public pybricksdev transports."""

from little_tinker_rig.i18n import tr


def find_hub(selector=None):
    """Prefer CDC devices; retain the public legacy USB adapter as a fallback."""
    from pybricksdev.usb import (
        EV3_USB_PID,
        LEGO_USB_VID,
        MINDSTORMS_INVENTOR_USB_PID,
        SPIKE_ESSENTIAL_USB_PID,
        SPIKE_PRIME_USB_PID,
    )
    from serial.tools.list_ports import comports

    ports = [
        port
        for port in comports()
        if port.vid == LEGO_USB_VID
        and port.pid
        in (
            EV3_USB_PID,
            SPIKE_PRIME_USB_PID,
            SPIKE_ESSENTIAL_USB_PID,
            MINDSTORMS_INVENTOR_USB_PID,
        )
        and (not selector or selector in (port.device, port.serial_number))
    ]
    if len(ports) > 1:
        raise ValueError(
            tr("Choose a USB port: {ports}").format(
                ports=", ".join(port.device for port in ports)
            )
        )
    if ports:
        try:
            from pybricksdev.connections.serial import PybricksHubSerial
        except ImportError as error:
            raise RuntimeError(
                tr(
                    "USB Serial requires the pinned pybricksdev fork. Run uv sync --locked --extra pybricks with your other extras from the project directory."
                )
            ) from error
        return PybricksHubSerial(ports[0].device)

    from pybricksdev.connections.pybricks import PybricksHubUSB
    from usb.core import find

    devices = list(
        find(
            find_all=True,
            idVendor=LEGO_USB_VID,
            custom_match=lambda device: (device.product or "").endswith("Pybricks")
            and (not selector or selector in (device.product, device.serial_number)),
        )
    )
    if len(devices) != 1:
        raise ValueError(tr("Connect exactly one Pybricks USB hub or specify its port"))
    return PybricksHubUSB(devices[0])
