#!/usr/bin/env python
# encoding: utf-8
#
# Copyright 2006 David Anderson <dave at natulte.net>

import os
import os.path
import sys
import optparse

# Waf removes the current dir from the python path. We readd it to
# import xmmsenv stuff.
sys.path = [os.getcwd()]+sys.path

from xmmsenv import sets # We have our own sets, to not depend on py2.4
from xmmsenv import gittools

import Params
import Object

VERSION="0.2 DrGonzo+WIP (git commit: %s)" % gittools.get_info_str()
APPNAME='xmms2'

srcdir='.'
blddir = '_build_'

####
## Initialization
####
def init():
  import gc
  gc.disable()

optional_subdirs = ["src/clients/cli",
                    "src/clients/et",
                    "src/clients/mdns/dns_sd",
                    "src/clients/mdns/avahi",
                    "src/clients/lib/xmmsclient++",
                    "src/clients/lib/xmmsclient++-glib",
                    "src/clients/lib/python",
                    "src/clients/lib/ruby"]

all_plugins = sets.Set([p for p in os.listdir("src/plugins")
                        if os.path.exists(os.path.join("src/plugins",
                                                       p,"wscript"))])

####
## Build
####
def build(bld):
#  bld.set_variants('default debug')

  # Build the XMMS2 defs file
#  defs = bld.create_obj('subst', 'uh')
#  defs.source = 'src/include/xmms/xmms_defs.h.in'
#  defs.target = 'src/include/xmms/xmms_defs.h'
#  defs.dict = bld.env_of_name('default')['XMMS_DEFS']

  # Process subfolders
  bld.add_subdirs('src/lib/xmmssocket src/lib/xmmsipc src/lib/xmmsutils src/xmms')

  # Build configured plugins
  plugins = bld.env_of_name('default')['XMMS_PLUGINS_ENABLED']
  bld.add_subdirs(["src/plugins/%s" % plugin for plugin in plugins])

  # Build the client libs
  bld.add_subdirs('src/clients/lib/xmmsclient')
  bld.add_subdirs('src/clients/lib/xmmsclient-glib')

  # Build the clients
  bld.add_subdirs(bld.env_of_name('default')['XMMS_OPTIONAL_BUILD'])

  # Headers
  bld.add_subdirs('src/include')

  # pkg-config
  o = bld.create_obj('pkgc')
  o.version = VERSION
  o.libs = bld.env_of_name('default')['XMMS_PKGCONF_FILES']


####
## Configuration
####
def _set_defs(conf):
  """Set the values needed by xmms_defs.h.in in the environment."""

  defs = {}

  platform_names = ['linux', 'freebsd', 'openbsd',
                    'netbsd', 'dragonfly', 'darwin']
  for platform in platform_names:
    if sys.platform.startswith(platform):
      defs["XMMS_OS_%s" % platform.upper()] = 1
      break
  defs['XMMS_VERSION'] = VERSION
  defs['PKGLIBDIR'] = os.path.join(conf.env['PREFIX'],
                                   'lib', 'xmms2')
  defs['BINDIR'] = os.path.join(conf.env['PREFIX'],
                                'bin')
  defs['SHAREDDIR'] = os.path.join(conf.env['PREFIX'],
                                  'share', 'xmms2')

  l = conf.env['XMMS_OUTPUT_PLUGINS']
  l.sort()
  l.reverse()
  defs['XMMS_OUTPUT_DEFAULT'] = l.pop(0)[1]
  defs['USERCONFDIR'] = '.config/xmms2'
  defs['SYSCONFDIR'] = '/etc/xmms2'

  conf.env['XMMS_DEFS'] = defs
  conf.env['PLUGINDIR'] = defs['PKGLIBDIR']
  conf.env['PKGCONFIGDIR'] = os.path.join(conf.env["PREFIX"], "lib", "pkgconfig")

  for i in defs:
    conf.add_define(i, defs[i])
  conf.write_config_header('src/include/xmms/xmms_defs.h')

def _configure_optionals(conf):
  """Process the optional xmms2 subprojects"""

  conf.env['XMMS_OPTIONAL_BUILD'] = []
  for o in optional_subdirs:
    if conf.sub_config(o):
      conf.env['XMMS_OPTIONAL_BUILD'].append(o)

  disabled_optionals = sets.Set(optional_subdirs)
  disabled_optionals.difference_update(conf.env['XMMS_OPTIONAL_BUILD'])

  return conf.env['XMMS_OPTIONAL_BUILD'], disabled_optionals

def _configure_plugins(conf):
  """Process all xmms2d plugins"""
  def _check_exist(plugins, msg):
    unknown_plugins = plugins.difference(all_plugins)
    if unknown_plugins:
      Params.fatal(msg % {'unknown_plugins': ', '.join(unknown_plugins)})
    return plugins

  conf.env['XMMS_PLUGINS_ENABLED'] = []

  # If an explicit list was provided, only try to process that
  if Params.g_options.enable_plugins:
    selected_plugins = _check_exist(sets.Set(Params.g_options.enable_plugins),
                                    "The following plugin(s) were requested, "
                                    "but don't exist: %(unknown_plugins)s")
    disabled_plugins = all_plugins.difference(selected_plugins)
    plugins_must_work = True
  # If a disable list was provided, we try all plugins except for those.
  elif Params.g_options.disable_plugins:
    disabled_plugins = _check_exist(sets.Set(Params.g_options.disable_plugins),
                                    "The following plugins(s) were disabled, "
                                    "but don't exist: %(unknown_plugins)s")
    selected_plugins = all_plugins.difference(disabled_plugins)
    plugins_must_work = False
  # Else, we try all plugins.
  else:
    selected_plugins = all_plugins
    disabled_plugins = sets.Set()
    plugins_must_work = False


  for plugin in selected_plugins:
    conf.sub_config("src/plugins/%s" % plugin)
    if (not conf.env["XMMS_PLUGINS_ENABLED"] or
        (len(conf.env["XMMS_PLUGINS_ENABLED"]) > 0
         and conf.env['XMMS_PLUGINS_ENABLED'][-1] != plugin)):
      disabled_plugins.add(plugin)

  # If something failed and we don't tolerate failure...
  if plugins_must_work:
    broken_plugins = selected_plugins.intersection(disabled_plugins)
    if broken_plugins:
      Params.fatal("The following required plugin(s) failed to configure: "
                   "%s" % ', '.join(broken_plugins))

  return conf.env['XMMS_PLUGINS_ENABLED'], disabled_plugins

def _output_summary(enabled_plugins, disabled_plugins,
                    enabled_optionals, disabled_optionals):
  print "\nOptional configuration:\n======================"
  print " Enabled:",
  Params.pprint('BLUE', ', '.join(enabled_optionals))
  print " Disabled:",
  Params.pprint('BLUE', ", ".join(disabled_optionals))
  print "\nPlugins configuration:\n======================"
  print " Enabled:",
  Params.pprint('BLUE', ", ".join(enabled_plugins))
  print " Disabled:",
  Params.pprint('BLUE', ", ".join(disabled_plugins))

def configure(conf):
  if (conf.check_tool('g++')):
    conf.env["HAVE_CXX"] = True
  else:
  	conf.env["HAVE_CXX"] = False
  conf.check_tool('gcc')
  conf.check_tool('pkgconfig', tooldir=os.path.abspath('xmmsenv'))

  conf.env["CCFLAGS"] += ['-g', '-O0']
  conf.env["CXXFLAGS"] += ['-g', '-O0']
  conf.env['XMMS_PKGCONF_FILES'] = []
  conf.env['XMMS_OUTPUT_PLUGINS'] = []

  if Params.g_options.config_prefix:
    conf.env["LIBPATH"] += [os.path.join(Params.g_options.config_prefix,
                                         "lib")]
    include = "-I%s" % os.path.join(Params.g_options.config_prefix,
                                    "include")
    conf.env["CCFLAGS"] += [include]
    conf.env["CXXFLAGS"] += [include]

  # Check for support for the generic platform
  has_platform_support = os.name in ('nt', 'posix')
  conf.check_message("platform code for", os.name,
                     has_platform_support)
  if not has_platform_support:
    Params.fatal("xmms2 only has platform support for Windows "
                 "and POSIX operating systems.")

  # Glib is required by everyone, so check for it here and let them
  # assume its presence.
  conf.check_tool('checks')
  conf.check_pkg2('glib-2.0', version='2.6.0', uselib='glib2')

  conf.sub_config('src/lib/xmmssocket')
  conf.sub_config('src/lib/xmmsipc')
  conf.sub_config('src/xmms')
  conf.sub_config('src/clients/lib/xmmsclient-glib')

  enabled_plugins, disabled_plugins = _configure_plugins(conf)
  enabled_optionals, disabled_optionals = _configure_optionals(conf)
  _output_summary(enabled_plugins, disabled_plugins,
                  enabled_optionals, disabled_optionals)
  _set_defs(conf)
  print "\nDefault output plugin: ",
  Params.pprint('BLUE', conf.env["XMMS_DEFS"]['XMMS_OUTPUT_DEFAULT'])

####
## Options
####
def _list_cb(option, opt, value, parser):
  """Callback that lets you specify lists of targets."""
  vals = value.split(',')
  if getattr(parser.values, option.dest):
    vals += getattr(parser.values, option.dest)
  setattr(parser.values, option.dest, vals)

def set_options(opt):
  opt.tool_options('gcc')
  opt.add_option('--with-plugins', action="callback", callback=_list_cb,
                 type="string", dest="enable_plugins")
  opt.add_option('--without-plugins', action="callback", callback=_list_cb,
                 type="string", dest="disable_plugins")
  opt.add_option('--conf-prefix', type='string', dest='config_prefix')
  for o in optional_subdirs:
    opt.sub_options(o)
