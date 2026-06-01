from gkbus.hardware import CanHardware
from gkbus.transport import Kwp2000OverCanTransport
from gkbus.protocol import kwp2000
from data_types import Module, Dtc, Protocol


class EcuConnection:
    def __init__(self, module: Module, interface: str = 'can0'):
        self.module = module
        self.interface = interface
        self.bus = None

    def connect(self) -> None:
        cs = self.module.communication_setup

        if cs.protocol in (Protocol.CAN, Protocol.ISO_15765):
            self._connect_can()
        elif cs.protocol in (Protocol.ISO_14230, Protocol.ISO_9141):
            raise NotImplementedError(
                f'K-line protocol {cs.protocol.name} not yet supported'
            )
        else:
            raise NotImplementedError(f'Protocol {cs.protocol.name} not supported')

    def _connect_can(self) -> None:
        cs = self.module.communication_setup
        hardware = CanHardware(self.interface)
        transport = Kwp2000OverCanTransport(hardware, tx_id=cs.tx_id, rx_id=cs.rx_id)
        self.bus = kwp2000.Kwp2000Protocol(transport)
        self.bus.init(
            kwp2000.commands.StartCommunication(),
            keepalive_command=kwp2000.commands.TesterPresent(
                kwp2000.enums.ResponseType.NOT_REQUIRED
            ),
            keepalive_delay=1.5,
        )

    def disconnect(self) -> None:
        if self.bus is not None:
            self.bus.close()
            self.bus = None

    def read_dtcs(self) -> list[Dtc]:
        """Read DTCs from the connected ECU and return them matched
        against the module's known DTC list."""
        if self.bus is None:
            raise RuntimeError('Not connected - call connect() first')

        cmd = kwp2000.commands.ReadDTCsByStatus(
            status=kwp2000.enums.DtcStatus.REQUEST_IDENTIFIED_DTC_AND_STATUS,
            group=kwp2000.enums.DtcGroup.ALL,
        )
        response = self.bus.execute(cmd).get_data()

        count = response[0]
        found = []
        for i in range(count):
            offset = 1 + i * 3
            code = self._decode_dtc_code(response[offset:offset + 2])
            status = response[offset + 2]
            matched = self._match_dtc(code)
            if matched is not None:
                matched.status = status
                found.append(matched)
            else:
                found.append(Dtc(
                    header=code,
                    index=code,
                    mask=None,
                    freeze_index='',
                    description=None,
                    status=status
                ))
        return found
    
    def _decode_dtc_code(self, code_bytes: bytes) -> str:
        """Convert 2 raw bytes to standard P/B/C/U-prefixed string."""
        high = code_bytes[0]
        family = ['P', 'C', 'B', 'U'][high >> 6]
        number = ((high & 0x3F) << 8) | code_bytes[1]
        return f'{family}{number:04X}'

    def _match_dtc(self, code: str) -> Dtc | None:
        """Find a Dtc in the module's list matching this code,
        handling base-vs-suffixed code matching."""
        for dtc in self.module.dtcs:
            if dtc.header == code or dtc.header.split('-')[0] == code:
                return dtc
        return None