from debian import deb822
import re
import gzip
import lzma
import tarfile
import subprocess
import hashlib
import glob

pkgver_base = "16.30.3"
pkgver_build = "315407"
pkgrel = 2

pkgver = "{0}.{1}".format(pkgver_base, pkgver_build)
url_ref="http://support.amd.com/en-us/kb-articles/Pages/AMDGPU-PRO-Beta-Driver-for-Vulkan-Release-Notes.aspx"
dlagents="https::/usr/bin/wget --referer {0} -N %u".format(url_ref)

source_url = "https://www2.ati.com/drivers/linux/amdgpu-pro_{0}-{1}.tar.xz".format(pkgver_base, pkgver_build)

subprocess.run(["/usr/bin/wget", "--referer", url_ref, "-N", source_url])
source_file = "amdgpu-pro_{0}-{1}.tar.xz".format(pkgver_base, pkgver_build)

def hashFile(file):
    block = 64 * 1024
    hash = hashlib.sha256()
    with open(file, 'rb') as f:
	    buf = f.read(block)
	    while len(buf) > 0:
		    hash.update(buf)
		    buf = f.read(block)
    return hash.hexdigest()

sources = [ source_url ]
sha5sums = [ hashFile(source_file) ]

patches = sorted(glob.glob("*.patch"))

for patch in patches:
    sources.append(patch)
    sha5sums.append(hashFile(patch))

header_tpl = """# Author: Janusz Lewandowski <lew21@xtreeme.org>
# Maintainer: David McFarland <corngood@gmail.com>
# Autogenerated from AMD's Packages file

pkgbase=amdgpu-pro-installer
pkgname={package_names}
if [ "$ALL_PACKAGES" = "true" ]; then
	pkgname+={optional_names}
fi
pkgver={pkgver}
pkgrel={pkgrel}
arch=('x86_64')
url='http://www.amd.com'
license=('custom:AMD')
makedepends=('wget')

DLAGENTS='{dlagents}'

source=({source})
sha256sums=({sha5sums})
"""

package_header_tpl = """
package_{NAME} () {{
	pkgdesc={DESC}
	depends={DEPENDS}
	arch=('{ARCH}')

	rm -Rf "${{srcdir}}"/{Package}_{Version}_{Architecture}
	mkdir "${{srcdir}}"/{Package}_{Version}_{Architecture}
	cd "${{srcdir}}"/{Package}_{Version}_{Architecture}
	ar x "${{srcdir}}"/amdgpu-pro-driver/{Filename}
	tar -C "${{pkgdir}}" -xf data.tar.xz
"""

package_header_i386 = """
	if [ -d "${pkgdir}/usr/lib/i386-linux-gnu" ]; then
		mkdir -p "${pkgdir}"/usr/lib32
		mv "${pkgdir}"/usr/lib/i386-linux-gnu/* "${pkgdir}"/usr/lib32
		rmdir "${pkgdir}"/usr/lib/i386-linux-gnu
	fi
"""

package_header_x86_64 = """
	if [ -d "${pkgdir}/usr/lib/x86_64-linux-gnu" ]; then
		mkdir -p "${pkgdir}"/usr/lib
		mv "${pkgdir}"/usr/lib/x86_64-linux-gnu/* "${pkgdir}"/usr/lib
		rmdir "${pkgdir}"/usr/lib/x86_64-linux-gnu
	fi
"""

package_footer = """}
"""

special_ops = {
	"amdgpu-pro-graphics": """
	provides=('libgl')
	conflicts=('libgl')
""",
	"lib32-amdgpu-pro-lib32": """
	provides=('lib32-libgl')
	conflicts=('lib32-libgl')
""",
	"amdgpu-pro-core": """
	mv ${pkgdir}/lib ${pkgdir}/usr/
	sed -i 's/\/usr\/lib\/x86_64-linux-gnu\//\/usr\/lib\//' ${pkgdir}/usr/lib/amdgpu-pro/ld.conf
	sed -i 's/\/usr\/lib\/i386-linux-gnu\//\/usr\/lib32\//' ${pkgdir}/usr/lib/amdgpu-pro/ld.conf
	mkdir -p ${pkgdir}/etc/ld.so.conf.d/
	ln -s /usr/lib/amdgpu-pro/ld.conf ${pkgdir}/etc/ld.so.conf.d/10-amdgpu-pro.conf
	mkdir -p ${pkgdir}/etc/modprobe.d/
	ln -s /usr/lib/amdgpu-pro/modprobe.conf ${pkgdir}/etc/modprobe.d/amdgpu-pro.conf
	install=amdgpu-pro-core.install
""",
	"amdgpu-pro-dkms":
	    "\t(cd ${{pkgdir}}/usr/src/amdgpu-pro-{0}-{1};\n".format(pkgver_base, pkgver_build) +
	    "\t\tsed -i 's/\/extra/\/extramodules/' dkms.conf\n" +
	    ";\n".join(["\t\tpatch -p1 -i \"${{srcdir}}/{0}\"".format(patch) for patch in patches]) +
	    ")\n",
	"amdgpu-pro-firmware": """
	mv ${pkgdir}/lib ${pkgdir}/usr/
	mv ${pkgdir}/usr/lib/firmware ${pkgdir}/usr/lib/firmware.tmp
	mkdir -p ${pkgdir}/usr/lib/firmware
	mv ${pkgdir}/usr/lib/firmware.tmp ${pkgdir}/usr/lib/firmware/updates
""",
	"xserver-xorg-video-amdgpu-pro": """
	mkdir -p ${pkgdir}/usr/lib/x86_64-linux-gnu
	# This is needed because libglx.so has a hardcoded DRI_DRIVER_PATH
	ln -s /usr/lib/dri ${pkgdir}/usr/lib/x86_64-linux-gnu/dri
	mv ${pkgdir}/usr/lib/amdgpu-pro/1.18/ ${pkgdir}/usr/lib/xorg
	rm -r ${pkgdir}/usr/lib/amdgpu-pro
""",
	"libegl1-amdgpu-pro-dev": """
	mv ${pkgdir}/usr/lib/amdgpu-pro/libEGL* ${pkgdir}/usr/lib
	rm -r ${pkgdir}/usr/lib/amdgpu-pro
""",
	"libegl1-amdgpu-pro": """
	mv ${pkgdir}/usr/lib/amdgpu-pro/libEGL* ${pkgdir}/usr/lib
	rm -r ${pkgdir}/usr/lib/amdgpu-pro
""",
	"libgl1-amdgpu-pro-dev": """
	mv ${pkgdir}/usr/lib/amdgpu-pro/libGL* ${pkgdir}/usr/lib
	rm -r ${pkgdir}/usr/lib/amdgpu-pro
""",
	"libgl1-amdgpu-pro-glx": """
	mv ${pkgdir}/usr/lib/amdgpu-pro/libGL* ${pkgdir}/usr/lib
	rm -r ${pkgdir}/usr/lib/amdgpu-pro
""",
	"libgles2-amdgpu-pro-dev": """
	mv ${pkgdir}/usr/lib/amdgpu-pro/libGLES* ${pkgdir}/usr/lib
	rm -r ${pkgdir}/usr/lib/amdgpu-pro
""",

	"lib32-libegl1-amdgpu-pro-dev": """
	mv ${pkgdir}/usr/lib32/amdgpu-pro/libEGL* ${pkgdir}/usr/lib32
	rm -r ${pkgdir}/usr/lib32/amdgpu-pro
""",
	"lib32-libegl1-amdgpu-pro": """
	mv ${pkgdir}/usr/lib32/amdgpu-pro/libEGL* ${pkgdir}/usr/lib32
	rm -r ${pkgdir}/usr/lib32/amdgpu-pro
""",
	"lib32-libgl1-amdgpu-pro-dev": """
	mv ${pkgdir}/usr/lib32/amdgpu-pro/libGL* ${pkgdir}/usr/lib32
	rm -r ${pkgdir}/usr/lib32/amdgpu-pro
""",
	"lib32-libgl1-amdgpu-pro-glx": """
	mv ${pkgdir}/usr/lib32/amdgpu-pro/libGL* ${pkgdir}/usr/lib32
	rm -r ${pkgdir}/usr/lib32/amdgpu-pro
""",
	"lib32-libgles2-amdgpu-pro-dev": """
	mv ${pkgdir}/usr/lib32/amdgpu-pro/libGLES* ${pkgdir}/usr/lib32
	rm -r ${pkgdir}/usr/lib32/amdgpu-pro
""",

	"amdgpu-pro-vulkan-driver": """
	sed -i 's/\/usr\/lib\/x86_64-linux-gnu\//\/usr\/lib\//' ${pkgdir}/etc/vulkan/icd.d/amd_icd64.json
""",
	"lib32-amdgpu-pro-vulkan-driver": """
	sed -i 's/\/usr\/lib\/i386-linux-gnu\//\/usr\/lib32\//' ${pkgdir}/etc/vulkan/icd.d/amd_icd32.json
""",

	"amdgpu-pro-libopencl-dev": """
	provides=(libcl)
	conflicts=(libcl)
""",
	"lib32-amdgpu-pro-libopencl-dev": """
	provides=(lib32-libcl)
	conflicts=(lib32-libcl)
""",
}

replace_deps = {
	"libc6": None,
	"libgcc1": None,
	"libstdc++6": None,
	"libx11-6": "libx11",
	"libx11-xcb1": None,
	"libxcb-dri2-0": "libxcb",
	"libxcb-dri3-0": "libxcb",
	"libxcb-present0": "libxcb",
	"libxcb-sync1": "libxcb",
	"libxcb-glx0": "libxcb",
	"libxcb1": "libxcb",
	"libxext6": "libxext",
	"libxshmfence1": "libxshmfence",
	"libxdamage1": "libxdamage",
	"libxfixes3": "libxfixes",
	"libxxf86vm1": "libxxf86vm",
	"libudev1": "libsystemd",
	"libpciaccess0": "libpciaccess",
	"libepoxy0": "libepoxy",
	"libelf1": None, # no lib32- package in Arch, just disabling for now
	"xserver-xorg-core": "xorg-server",
	"libcunit1": "cunit",
	"libdrm-radeon1": "libdrm",
	"amdgpu-pro-firmware": "linux-firmware",
	"libssl1.0.0": "openssl",
	"zlib1g": "zlib",
}

replace_version = {
	"linux-firmware": "",
}

dependency = re.compile(r"([^ ]+)(?: \((.+)\))?")

arch_map = {
	"amd64": "x86_64",
	"i386": "i686",
	"all": "any"
}

optional_packages = frozenset([
])

disabled_packages = frozenset([
])

deb_archs={}

def quote(string):
	return "\"" + string.replace("\\", "\\\\").replace("\"", "\\\"") + "\""

def convertName(name, info):
	if info["Architecture"] == "i386" and (name not in deb_archs or "any" not in deb_archs[name]):
		return "lib32-" + name
	return name

def convertVersionSpecifier(name, spec, names):
	if name in replace_version:
		return replace_version[name]
	if name in names:
		return "=" + pkgver + "-" + str(pkgrel)
	if not spec:
		return ""

	sign, spec = spec.split(" ", 1)

	spec = spec.strip()
	if ":" in spec:
		whatever, spec = spec.rsplit(":", 1)
	return sign + spec

def convertPackage(info, names):
	if info["Architecture"] == "i386":
		name = "lib32-" + info["Package"]
		arch = "x86_64"
	else:
		name = info["Package"]
		arch = arch_map[info["Architecture"]]

	try:
		deps = info["Depends"].split(", ")
	except:
		deps = []

	deps = [dependency.match(dep).groups() for dep in deps]
	deps = [(replace_deps[name] if name in replace_deps else name, version) for name, version in deps]
	deps = ["'" + convertName(name, info) + convertVersionSpecifier(name, version, names) + "'" for name, version in deps if name]
	deps2 = []
	for dep in deps:
		if not dep in deps2:
			deps2.append(dep)
	deps = "(" + " ".join(deps2) + ")"

	special_op = special_ops[name] if name in special_ops else ""

	desc = info["Description"].split("\n")
	if len(desc) > 2:
		desc = desc[0]
	else:
		desc = " ".join(x.strip() for x in desc)

	ret = package_header_tpl.format(DEPENDS=deps, NAME=name, ARCH=arch, DESC=quote(desc), **info)

	if info["Architecture"] == "i386":
		ret += package_header_i386
	else:
		ret += package_header_x86_64

	if special_op:
		ret += special_op + "\n"
	if info["Architecture"] == "i386":
		ret += "\trm -Rf ${pkgdir}/usr/share/doc ${pkgdir}/usr/include\n"
	ret += package_footer

	return ret

def writePackages(f):
	package_list=[]
	package_names=[]
	optional_names=[]

	for info in deb822.Packages.iter_paragraphs(f):
		if not info["Package"] in deb_archs:
			deb_archs[info["Package"]] = set()

		deb_archs[info["Package"]].add(info["Architecture"])

		name = "lib32-" + info["Package"] if info["Architecture"] == "i386" else info["Package"]

		if info["Package"] in disabled_packages:
			continue
		elif info["Package"] in optional_packages:
			optional_names.append(name)
		else:
			package_names.append(name)

		package_list.append(info)

	names = ["lib32-" + info["Package"] if info["Architecture"] == "i386" else info["Package"] for info in package_list]

	print(header_tpl.format(package_names="(" + " ".join(package_names) + ")",
				optional_names="(" + " ".join(optional_names) + ")",
				pkgver=pkgver, pkgrel=pkgrel,
				dlagents=dlagents, source="\n\t".join(sources), sha5sums="\n\t".join(sha5sums)))

	f.seek(0)

	for info in package_list:
		print(convertPackage(info, package_names + optional_names))

with lzma.open(source_file, "r") as tar:
	with tarfile.open(fileobj=tar) as tf:
		with tf.extractfile("amdgpu-pro-driver/Packages.gz") as gz:
			with gzip.open(gz, "r") as packages:
				writePackages(packages)
