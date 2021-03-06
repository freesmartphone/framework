#!/usr/bin/env python
"""
SMS Testsuite

(C) 2009 Daniel Willmann <daniel@totalueberwachung.de>
GPLv2 or later
"""


import unittest
import gobject
import threading
import dbus
from dbus.mainloop.glib import DBusGMainLoop
DBusGMainLoop(set_as_default=True)

# Add ogsmd stuff to PYTHONPATH
import sys
sys.path.extend(["../", "../framework/subsystems/"])

import test
import datetime
import framework.patterns.tasklet as tasklet
from framework.subsystems.ogsmd.gsm.sms import *

class SMSTests(unittest.TestCase):
    """Some test cases for the sms subsystem"""
    def setUp(self):
        # This sms-deliver PDU would be reencoded with a different length value
        # "07918167830071F1040BD0C7F7FBCC2E0300008080203200748078D0473BED2697D9F3B20E442DCFE9A076793E0F9FCBA07B9A8E0691C3EEF41C0D1AA3C3F2F0985E96CF75A00EE301E22C1C2C109B217781642E50B87E76816433DD0C066A81E60CB70B347381C2F5B30B"
        self.pdus_sms_deliver = [
        "0791448720900253040C914497035290960000500151614414400DD4F29C9E769F41E17338ED06",
        "0791448720003023440C91449703529096000050015132532240A00500037A020190E9339A9D3EA3E920FA1B1466B341E472193E079DD3EE73D85DA7EB41E7B41C1407C1CBF43228CC26E3416137390F3AABCFEAB3FAAC3EABCFEAB3FAAC3EABCFEAB3FAAC3EABCFEAB3FADC3EB7CFED73FBDC3EBF5D4416D9457411596457137D87B7E16438194E86BBCF6D16D9055D429548A28BE822BA882E6370196C2A8950E291E822BA88",
        "0791448720003023440C91449703529096000050015132537240310500037A02025C4417D1D52422894EE5B17824BA8EC423F1483C129BC725315464118FCDE011247C4A8B44",
        "07914477790706520414D06176198F0EE361F2321900005001610013334014C324350B9287D12079180D92A3416134480E",
        "0791448720003023440C91449703529096000050016121855140A005000301060190F5F31C447F83C8E5327CEE0221EBE73988FE0691CB65F8DC05028190F5F31C447F83C8E5327CEE028140C8FA790EA2BF41E472193E7781402064FD3C07D1DF2072B90C9FBB402010B27E9E83E86F10B95C86CF5D2064FD3C07D1DF2072B90C9FBB40C8FA790EA2BF41E472193E7781402064FD3C07D1DF2072B90C9FBB402010B27E9E83E8",
        "0791448720003023440C91449703529096000050016121850240A0050003010602DE2072B90C9FBB402010B27E9E83E86F10B95C86CF5D201008593FCF41F437885C2EC3E72E100884AC9FE720FA1B442E97E1731708593FCF41F437885C2EC3E72E100884AC9FE720FA1B442E97E17317080442D6CF7310FD0D2297CBF0B90B040221EBE73988FE0691CB65F8DC05028190F5F31C447F83C8E5327CEE028140C8FA790EA2BF41",
        "0791448720003023440C91449703529096000050016121854240A0050003010603C8E5327CEE0221EBE73988FE0691CB65F8DC05028190F5F31C447F83C8E5327CEE028140C8FA790EA2BF41E472193E7781402064FD3C07D1DF2072B90C9FBB402010B27E9E83E86F10B95C86CF5D201008593FCF41F437885C2EC3E72E10B27E9E83E86F10B95C86CF5D201008593FCF41F437885C2EC3E72E100884AC9FE720FA1B442E97E1",
        "0791448720003023400C91449703529096000050016121858240A0050003010604E62E100884AC9FE720FA1B442E97E17317080442D6CF7310FD0D2297CBF0B90B040221EBE73988FE0691CB65F8DC0542D6CF7310FD0D2297CBF0B90B040221EBE73988FE0691CB65F8DC05028190F5F31C447F83C8E5327CEE028140C8FA790EA2BF41E472193E7781402064FD3C07D1DF2072B90C9FBB402010B27E9E83E86F10B95C86CF5D",
        "0791448720003023400C91449703529096000050016121853340A005000301060540C8FA790EA2BF41E472193E7781402064FD3C07D1DF2072B90C9FBB402010B27E9E83E86F10B95C86CF5D201008593FCF41F437885C2EC3E72E100884AC9FE720FA1B442E97E17317080442D6CF7310FD0D2297CBF0B90B84AC9FE720FA1B442E97E17317080442D6CF7310FD0D2297CBF0B90B040221EBE73988FE0691CB65F8DC05028190",
        "0791448720003023440C914497035290960000500161218563402A050003010606EAE73988FE0691CB65F8DC05028190F5F31C447F83C8E5327CEE0281402010",
        "07918167830071F1040BD0C7F7FBCC2E030000808010800120804AD0473BED2697D9F3B20E644CCBDBE136835C6681CCF2B20B147381C2F5B30B04C3E96630500B1483E96030501A34CDB7C5E9B71B847AB2CB2062987D0E87E5E414",
        "0791447758100650040C9194714373238200008080312160304019D4F29C0E6A97E7F3F0B90CB2A7C3A0791A7E0ED3CB2E",
        "0791447758100650040DD0F334FC1CA6970100008080312170224008D4F29CDE0EA7D9",
        "0791889653704434040C9188969366423600008090017134632302CA34",
        "0791889663000009040C918896631009910008809061510540238453485B89FF0167094EF681C97D055FC38DF376844E8B548C4F608AAA54E6FF016709500B59735B69525B52A0516590FD6703753759738AAA60F389818A8D8B584F60FF0C624B6A5F5FEB64A500350032003163090033628A63E16A5F67038A8D8B5859793002621664A50035003200316309003251FA73FE611B60C5597D904B5146FF01",
        "0791889663000019040C918896631030990008809071619483234E60A86709672A63A54F8696FB003A000A00300039002F00310037002000300034003A003400330050004D4F8681EA0030003900380038003500360033003900390036002000280032901A0029000A",
        "0791889663000009040C918896631009910008809071717374238A7E415FD951B76DE1768457CE5E02FF0C4F609858610F548C6211505A670B53CB55CEFF1F624B6A5F76F464A500350032003163090031518D630900338F3851650033003200320030003000390033621167037B495F854F60771F5FC376844F8696FB007E621664A5003500320031630900328AC75FC3804A59298DA330014EA453CB8D855BB96613007E",
        "0791889663000009040C91889671342752000080908171153223282073788E4EBFDD2B1CCE96C3E16AB6592E67D32944ECF7780D9A8FE5E5B25BA468B514",
        "0791889663000019040C918896138188020008809091907405238050B38A0A606F003F767E842C734E91D190017D664F6076846D3B52D590FD958B8DD15169500B67084E86FF0C4F605831540D4E8655CEFF0173FE572853EA898150B34E00500B7A7A767D7C218A0A52300030003900330031002D003100380031003900330030514D8CBB5831540DFF0C6A5F67035C31662F4F6076845594FF01",
        "07918896532430280406918816880000809042215024235FC3309B0D42BEDB6590380F22A7C3ECB4FB0CE2AD7C20DEF85D77D3E579D0F84D2E836839900FC403C1D16F7719E47E837CA01D681866B341ECF738CC06A9EB733A889C0EB341ECF738CC06C1D16F7719E47EBB00",
        "07914140279505F74404D011002000800190819234000704010200018000",
        "07914140279505F74404D011002000800190913285000704010200028000",
        "07914140279505F74404D011002000800190320243000704010200038000",
        "0791947106004034040C9194713900303341008011311265854059D6B75B076A86D36CF11BEF024DD365103A2C2EBB413390BB5C2F839CE1315A9E1EA3E96537C805D2D6DBA0A0585E3797DDA0FB1ECD2EBB41D37419244ED3E965906845CBC56EB9190C069BCD6622",
        "0791947106004034040C9194713900303341008011312270804059D6B75B076A86D36CF11BEF024DD365103A2C2EBB413490BB5C2F839CE1315A9E1EA3E96537C805D2D6DBA0A0585E3797DDA0FB1ECD2EBB41D37419244ED3E965906845CBC56EB9190C069BCD6622",
        ]

        self.pdus_sms_submit = [
        "07910447946400F011000A9270042079330000AA0161",
        "079194710716000001310C919491103246570000061B1EBD3CA703",
        ]

        self.pdus_sms_submit_report = [
        "010080110191146140",
        "010080112102618040",
        ]

        self.pdus_sms_status_report = [
        "07919730071111F106BD0B919750673814F3902090127043219020901270142100",
        "079194710716000006B70C91943531946236903020308400409030203084004000"
        ]

        self.pdus_CB = [
        "001000DD001133DAED46ABD56AB5186CD668341A8D46A3D168341A8D46A3D168341A8D46A3D168341A8D46A3D168341A8D46A3D168341A8D46A3D168341A8D46A3D168341A8D46A3D168341A8D46A3D168341A8D46A3D100",
        ]
        self.decodePDUs = []

    def tearDown(self):
        pass

    def _recodepdu(self, pdu, dir):
        sms = SMS.decode(pdu, dir)
        genpdu = sms.pdu()
        self.assert_(pdu == genpdu, "Reencoded SMS doesn't match, PDUS:\n%s\n%s\n%s" % (repr(sms), pdu, genpdu))

    def test_recode_sms_deliver(self):
        """Try to decode sms-deliver messages and reencode them to see if they match"""
        for pdu in self.pdus_sms_deliver:
            self._recodepdu(pdu, "sms-deliver")

    def test_recode_sms_submit(self):
        """Try to decode sms-submit messages and reencode them to see if they match"""
        for pdu in self.pdus_sms_submit:
            self._recodepdu(pdu, "sms-submit")

    def test_recode_sms_submit_report(self):
        """Try to decode sms-submit-report messages and reencode them to see if they match"""
        for pdu in self.pdus_sms_submit_report:
            self._recodepdu(pdu, "sms-submit-report")

    def test_recode_sms_status_report(self):
        """Try to decode sms-status-report messages and reencode them to see if they match"""
        for pdu in self.pdus_sms_status_report:
            self._recodepdu(pdu, "sms-status-report")

    def test_decode_sms_deliver(self):
        """Try to decode some sms-deliver messages"""
        for pdu in self.pdus_sms_deliver:
            SMS.decode(pdu, "sms-deliver")

    def test_decode_sms_submit(self):
        """Try to decode some sms-submit messages"""
        for pdu in self.pdus_sms_submit:
            SMS.decode(pdu, "sms-submit")

    def test_decode_sms_submit_report(self):
        """Try to decode some sms-submit-report messages"""
        for pdu in self.pdus_sms_submit_report:
            SMS.decode(pdu, "sms-submit-report")

    def test_decode_sms_status_report(self):
        """Try to decode some sms-status-report messages"""
        for pdu in self.pdus_sms_status_report:
            sms = SMS.decode(pdu, "sms-status-report")

    def test_decode_cb(self):
        """Try to decode CellBroadcast messages"""

        for pdu in self.pdus_CB:
            cb = CellBroadcast.decode(pdu)

    def test_default_sms_submit(self):
        """Check the default properties of an sms-submit message"""
        defprops = {'status-report-request': False, 'reject-duplicates': False, 'pid': 0, 'reply-path': False, 'message-reference': 0, 'alphabet': 'gsm_default', 'type': 'sms-submit'}
        sms = SMSSubmit()
        self.assert_(sms.properties == defprops, "Default sms-submit properties are wrong: %s" % sms.properties)

    def test_default_sms_deliver(self):
        """Check the default properties of an sms-deliver message"""
        defprops = {'status-report-indicator': False, 'more-messages-to-send': False, 'alphabet': 'gsm_default', 'pid': 0, 'reply-path': False, 'timestamp': 'Tue Jan  1 00:00:00 1980 +0000', 'type': 'sms-deliver'}
        sms = SMSDeliver()
        self.assert_(sms.properties == defprops, "Default sms-deliver properties are wrong: %s" % sms.properties)

    def test_default_sms_submit_report(self):
        """Check the default properties of an sms-submit-report message"""
        defprops = {'timestamp': 'Tue Jan  1 00:00:00 1980 +0000', 'type': 'sms-submit-report'}
        sms = SMSSubmitReport()
        self.assert_(sms.properties == defprops, "Default sms-submit-report properties are wrong: %s" % sms.properties)

    def test_default_sms_submit_report_err(self):
        """Check the default properties of an sms-submit-report message for RP-ERROR"""
        defprops = {'timestamp': 'Tue Jan  1 00:00:00 1980 +0000', 'type': 'sms-submit-report', 'fcs': 0xff, 'failure-cause': 'unspecified-error'}
        sms = SMSSubmitReport(False)
        self.assert_(sms.properties == defprops, "Default sms-submit-report properties are wrong: %s" % sms.properties)

    def test_default_sms_status_report(self):
        """Check the default properties of an sms-status-report message"""
        defprops = {'status': 0, 'status-report-qualifier': 'sms-submit', 'more-messages-to-send': False, 'timestamp': 'Tue Jan  1 00:00:00 1980 +0000', 'status-message': 'Completed: Delivered', 'discharge-time': 'Tue Jan  1 00:00:00 1980 +0000', 'message-reference': 0, 'type': 'sms-status-report'}

        sms = SMSStatusReport()
        self.assert_(sms.properties == defprops, "Default sms-status-report properties are wrong: %s" % sms.properties)

    def test_generate_sms(self):
        """Create an SMS object and try to encode it"""
        defprops = {'status-report-request': False, 'reject-duplicates': False, 'pid': 0, 'reply-path': False, 'message-reference': 0, 'alphabet': 'gsm_default', 'type': 'sms-submit'}
        sms = SMSSubmit()
        sms.addr = PDUAddress.guess("+491234")
        self.assert_(sms.pdu() == "0001000691942143000000",
                "SMS encoding incorrect, PDU is %s" %sms.pdu())
        sms.ud = "Test"
        self.assert_(sms.pdu() == "0001000691942143000004D4F29C0E",
                "SMS encoding incorrect, PDU is %s" %sms.pdu())
        sms.properties = { "pid": 10, "csm_id": 10, "csm_num": 2, "csm_seq" : 1}

        self.assert_(sms.pdu() == "00410006919421430A000B0500030A0201A8E5391D",
                "SMS encoding incorrect, PDU is %s" %sms.pdu())
        expected_props = defprops
        expected_props.update( { "pid": 10, "csm_id": 10, "csm_num": 2, "csm_seq" : 1} )
        self.assert_(sms.properties == expected_props, "SMS properties not as expected: %s" % sms.properties)

        # Extended plane
        sms.ud = "{}[]\\"
        self.assert_(sms.dcs_alphabet == "gsm_default",
                "SMS extended alphabet encoding failed, alphabet used is: %s"
                % sms.dcs_alphabet)
        self.assert_(sms.pdu() == "00410006919421430A00110500030A020136A84D6AC3DBF8362F",
                "SMS extended alphabet encoding failed, PDU:\n%s" % sms.pdu())

        # UCS-2
        sms.properties = { "alphabet": "ucs2" }
        sms.ud = u'Unicode\u2320'
        self.assert_(sms.dcs_alphabet == "utf_16_be",
                "SMS UCS2 alphabet encoding failed, alphabet used is: %s"
                % sms.dcs_alphabet)
        self.assert_(sms.pdu() == "00410006919421430A08160500030A02010055006E00690063006F006400652320",
                "SMS UCS2 alphabet encoding failed, PDU:\n%s" % sms.pdu())

    def test_udh_port_8(self):
        """Test setting and getting ports via the userdata header (8-bit)"""
        sms = SMSSubmit()
        sms.properties = { "src_port": 10, "dst_port": 80, "port_size": 8 }

        self.assert_(4 in sms.udh, "UDH information element 4 not found")
        self.assert_(sms.udh[4] == [80, 10], "Data in UDH information element 4 is wrong: %s" % sms.udh[4])

    def test_udh_port_16(self):
        """Test setting and getting ports via the userdata header (16-bit)"""
        sms = SMSSubmit()
        sms.properties = { "src_port": 1028, "dst_port": 80, "port_size": 16 }

        self.assert_(5 in sms.udh, "UDH information element 5 not found")
        self.assert_(sms.udh[5] == [0, 80, 1028/256, 1028%256], "Data in UDH information element 5 is wrong: %s" % sms.udh[5])

    def test_udh_csm_short(self):
        """Test concatenated short message settings (8-bit ID) via userdata header"""
        sms = SMSSubmit()
        sms.properties = { "csm_id": 80, "csm_num": 2, "csm_seq":1 }

        self.assert_(0 in sms.udh, "UDH information element 0 not found")
        self.assert_(sms.udh[0] == [80, 2, 1], "Data in UDH information element 0 is wrong: %s" % sms.udh[0])

    def test_udh_csm_long(self):
        """Test concatenated short message settings (16-bit ID) via userdata header"""
        sms = SMSSubmit()
        sms.properties = { "csm_id": 1080, "csm_num": 2, "csm_seq":1 }

        self.assert_(8 in sms.udh, "UDH information element 0 not found")
        self.assert_(sms.udh[8] == [1080/256, 1080%256, 2, 1], "Data in UDH information element 8 is wrong: %s" % sms.udh[8])

    def test_invalid_scts_date_in_pdu(self):
        """Ensure invalid dates don't break SMS decoding"""

        invalid_date_pdu = "07914140279505F74404D011002000803190819234000704010200018000"
        sms = SMS.decode(invalid_date_pdu, "sms-deliver")
        self.assert_(sms.properties["timestamp"] == "Tue Jan  1 00:00:00 1980 +0000")
        self.assert_(sms.properties.has_key("error"))

    def test_profile_decoding(self):
        """See how long it takes for one sms-deliver to be decoded"""

        testpdu = "0791448720003023440C91449703529096000050016121855140A005000301060190F5F31C447F83C8E5327CEE0221EBE73988FE0691CB65F8DC05028190F5F31C447F83C8E5327CEE028140C8FA790EA2BF41E472193E7781402064FD3C07D1DF2072B90C9FBB402010B27E9E83E86F10B95C86CF5D2064FD3C07D1DF2072B90C9FBB40C8FA790EA2BF41E472193E7781402064FD3C07D1DF2072B90C9FBB402010B27E9E83E8"
        n = 200

        start = datetime.now()
        for i in range(n):
            sms = SMS.decode(testpdu, "sms-deliver")
        end = datetime.now()
        diff = end-start
        diff = (diff.seconds*1000 + diff.microseconds/1000.0)/n
        print "%.3fms ... " % diff

    def test_profile_encoding(self):
        """See how long it takes for one sms-deliver to be reencoded"""

        testpdu = "0791448720003023440C91449703529096000050016121855140A005000301060190F5F31C447F83C8E5327CEE0221EBE73988FE0691CB65F8DC05028190F5F31C447F83C8E5327CEE028140C8FA790EA2BF41E472193E7781402064FD3C07D1DF2072B90C9FBB402010B27E9E83E86F10B95C86CF5D2064FD3C07D1DF2072B90C9FBB40C8FA790EA2BF41E472193E7781402064FD3C07D1DF2072B90C9FBB402010B27E9E83E8"
        n = 200

        sms = SMS.decode(testpdu, "sms-deliver")
        start = datetime.now()
        for i in range(n):
            sms.pdu()
        end = datetime.now()
        diff = end-start
        diff = (diff.seconds*1000 + diff.microseconds/1000.0)/n
        print "%.3fms ... " % diff


if __name__ == '__main__':

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SMSTests)
    result = unittest.TextTestRunner(verbosity=3).run(suite)


#    #============================================================================#
#    def readFromFile( path ):
#    #============================================================================#
#        try:
#            value = open( path, 'r' ).read().strip()
#        except IOError, e:
#            print( "(could not read from '%s': %s)" % ( path, e ) )
#            return "N/A"
#        else:
#            return value
#
#
#    # Read PDUs from a file if passed as a parameter
#    if len(sys.argv) >= 2:
#        pdus_sms_deliver = readFromFile(sys.argv[1]).split("\n")
#    if len(sys.argv) == 3:
#        pdus_sms_submit = readFromFile(sys.argv[2]).split("\n")


# vim: expandtab shiftwidth=4 tabstop=4
