#include <sys/types.h>
#include <sys/ioctl.h>
#include <stdio.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>
#include <netdb.h>
#include <unistd.h>

#include <linux/if.h>
#include <linux/wireless.h>

int wifi_radio_is_on (const char *iface)
{
    struct iwreq wrq;
    int sock = socket (AF_INET, SOCK_DGRAM, 0);
    if (!sock)
    {
        perror( "Unable to open socket" );
        return 0;
    }

    memset (&wrq, 0, sizeof (struct iwreq));
    strncpy ((char *)&wrq.ifr_name, iface, IFNAMSIZ);

    if (ioctl (sock, SIOCGIWTXPOW, &wrq) != 0)
    {
        perror( "Error performing ioctl" );
        close (sock);
        return 0;
    }

    close (sock);

    return !wrq.u.txpower.disabled;
}

int wifi_radio_set_on (const char *iface, int enable)
{
    struct iwreq wrq;
    int sock = socket (AF_INET, SOCK_DGRAM, 0);
    if (!sock)
    {
        perror( "Unable to open socket" );
        return 0;
    }

    memset (&wrq, 0, sizeof (struct iwreq));
    strncpy ((char *)&wrq.ifr_name, iface, IFNAMSIZ);

    if (ioctl (sock, SIOCGIWTXPOW, &wrq) != 0)
    {
        perror( "Error performing ioctl" );
        close (sock);
        return 0;
    }

    if ( wrq.u.txpower.disabled != !enable )
    {
        wrq.u.txpower.disabled = !enable;

        if (ioctl (sock, SIOCSIWTXPOW, &wrq) != 0)
        {
            perror( "Error performing ioctl" );
            close (sock);
            return 0;
        }
    }

    close (sock);
    return 1;
}
