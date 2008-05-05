modems = {}
try:
    import testingmodem
except ImportError:
    pass
else:
    modems["testing"] = testingmodem.Modem

try:
    import ticalypso
except ImportError:
    pass
else:
    modems["ti_calypso"] = ticalypso.TiCalypsoModem

try:
    import genericmodem
except ImportError:
    pass
else:
    modems["generic"] = genericmodem.GenericModem


def allModems():
    return modems.keys()

def hasModem( m ):
    return m in modems

def modem( m ):
    return modems.get( m, None )
