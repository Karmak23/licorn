

sudo apt-get -qy --fix-missing --force-yes install nullmailer darcs \
                pyro python-gamin python-pylibacl python-ldap \
                python-xattr python-netifaces python-dumbnet \
                python-pyip python-ipcalc python-dbus python-gobject \
                python-udev

export LCN_DEV_DIR=`pwd`

for i in add mod del chk get
do
        sudo rm -f /usr/bin/${i}
        sudo ln -sf "${LCN_DEV_DIR}/interfaces/cli/${i}.py" /usr/bin/${i}
        sudo chmod a+x /usr/bin/${i}
done

sudo rm -f /usr/sbin/licornd
sudo ln -sf "${LCN_DEV_DIR}/daemon/main.py" /usr/sbin/licornd
sudo chmod a+x /usr/sbin/licornd

sudo mkdir /etc/licorn
sudo ln -sf "${LCN_DEV_DIR}/config/check.d" /etc/licorn

sudo mkdir -p /usr/share/licorn
sudo ln -sf "${LCN_DEV_DIR}/interfaces/wmi" /usr/share/licorn/wmi
sudo ln -sf "${LCN_DEV_DIR}/core/backends/schemas" \
        /usr/share/licorn/schemas
sudo ln -sf "${LCN_DEV_DIR}/locale/fr.mo" \
        /usr/share/locale/fr/LC_MESSAGES/licorn.mo

sudo ln -sf "${LCN_DEV_DIR}" /usr/lib/python2.6/dist-packages/licorn


sudo su - -c 'echo "licornd.role = SERVER" >> /etc/licorn/licorn.conf'
