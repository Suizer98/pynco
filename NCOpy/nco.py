from __future__ import print_function
import os
import re
import subprocess
import tempfile
import random
import string


class NCOException(Exception):
    def __init__(self, stdout, stderr, returncode):
        super(NCOException, self).__init__()
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
        self.msg = '(returncode:{0}) {1}'.format(returncode, stderr)

    def __str__(self):
        return self.msg


class Nco(object):
    def __init__(self, returnCdf=False, returnNoneOnError=False,
                 forceOutput=True, cdfMod='scipy', debug=0, **kwargs):

        operators = ['ncap2', 'ncatted', 'ncbo', 'nces', 'ncecat', 'ncflint',
                     'ncks', 'ncpdq', 'ncra', 'ncrcat', 'ncrename', 'ncwa',
                     'ncea', 'ncdump']

        if 'NCOpath' in os.environ:
            self.NCOpath = os.environ['NCOpath']
        else:
            self.NCOpath = os.path.split(which('ncks'))[0]

        self.operators = operators
        self.returnCdf = returnCdf
        self.returnNoneOnError = returnNoneOnError
        self.tempfile = MyTempfile()
        self.forceOutput = forceOutput
        self.cdfMod = cdfMod
        self.debug = debug
        self.outputOperatorsPattern = ['ncdump', '-H', '--data',
                                       '--hieronymus', '-M', '--Mtd',
                                       '--Metadata', '-m', '--mtd',
                                       '--metadata', '-P', '--prn', '--print',
                                       '-r', '--revision', '--vrs',
                                       '--version', '--u', '--units']

        if kwargs:
            self.options = kwargs
        else:
            self.options = None

    def __dir__(self):
        res = dir(type(self)) + list(self.__dict__.keys())
        res.extend(self.operators)
        return res

    def call(self, cmd, environment=None):
        if self.debug:
            print('# DEBUG ==================================================')
            if None != environment:
                for key, val in environment.items():
                    print("# DEBUG: ENV: {0} = {1}".format(key, val))
            print('# DEBUG: CALL>>'+' '.join(cmd))
            print('# DEBUG ==================================================')

        proc = subprocess.Popen(' '.join(cmd),
                                shell=True,
                                stderr=subprocess.PIPE,
                                stdout=subprocess.PIPE,
                                env=environment)
        retvals = proc.communicate()
        return {"stdout": retvals[0],
                "stderr": retvals[1],
                "returncode": proc.returncode}

    def hasError(self, method_name, cmd, retvals):
        if (self.debug):
            print("# DEBUG: RETURNCODE: {0}".format(retvals["returncode"]))
        if retvals["returncode"] != 0:
            print("Error in calling operator {0} with:".format(method_name))
            print(">>> {0} <<<".format(' '.join(cmd)))
            print(retvals["stderr"])
            return True
        else:
            return False

    def __getattr__(self, method_name):

        @auto_doc(method_name, self)
        def get(self, **kwargs):
            options = kwargs.pop('options', False)
            input = kwargs.pop("input", '')
            force = kwargs.pop("force", self.forceOutput)
            output = kwargs.pop("output", '')
            environment = kwargs.pop("env", None)
            returnCdf = kwargs.pop("returnCdf", False)
            returnArray = kwargs.pop("returnArray", False)
            returnMaArray = kwargs.pop("returnMaArray", False)
            operatorPrintsOut = kwargs.pop("operatorPrintsOut", False)

            #build the nco command
            #1. the nco operator
            cmd = [os.path.join(self.NCOpath, method_name)]

            #2a. options keyword arg
            if options:
                if isinstance(options, basestring):
                    cmd.extend(options.split())
                else:
                    #we assume it's either a list, a tuple or any iterable.
                    cmd.extend(options)

            if self.debug:
                if type(self.debug) == bool:
                    # assume debug level is 10
                    cmd.append('-D 10')
                elif type(self.debug) == int:
                    cmd.append('-D {0}'.format(self.debug))
                else:
                    raise TypeError('Unknown type for debug: \
                                    {0}'.format(type(self.debug)))

            #2b. all other keyword args become options
            if kwargs:
                for key, val in kwargs.iteritems():
                    if val and type(val) == bool:
                        cmd.append("--{}".format(key))
                    elif isinstance(val, basestring) or \
                            isinstance(val, int) or \
                            isinstance(val, float):
                        cmd.append("--{0}={1}".format(key, val))
                    else:
                        #we assume it's either a list, a tuple or any iterable.
                        cmd.append("--{0}={1}".format(key, ",".join(val)))

            #2c. Global options come in
            if self.options:
                for key, val in self.options.iteritems():
                    if val and type(val) == bool:
                        cmd.append("--"+key)
                    elif isinstance(val, basestring):
                        cmd.append("--{0}={1}".format(key, val))
                    else:
                        #we assume it's either a list, a tuple or any iterable.
                        cmd.append("--{0}={1}".format(key, ",".join(val)))

            #3. input files or operators
            if input:
                if isinstance(input, basestring):
                    cmd.append(input)
                else:
                    #we assume it's either a list, a tuple or any iterable.
                    cmd.extend(input)
            else:
                raise KeyError('Must include input keyword argument to all\
                                Nco.nco method calls')

            # Check if operator prints out
            for piece in cmd:
                if piece in self.outputOperatorsPattern or \
                        method_name == 'ncdump':
                    operatorPrintsOut = True

            if operatorPrintsOut:
                retvals = self.call(cmd)
                if not self.hasError(method_name, cmd, retvals):
                    r = map(string.strip, retvals["stdout"].split(os.linesep))
                    return r[:len(r)-1]
                else:
                    if self.returnNoneOnError:
                        return None
                    else:
                        raise NCOException(**retvals)
            else:
                if force and not os.path.isfile(output):
                    # 4. output file
                    if output:
                        if isinstance(output, basestring):
                            cmd.append(output)
                        else:
                            # we assume it's an iterable.
                            if len(output) > 1:
                                raise TypeError('Only one output allowed, \
                                                must be string or 1 length \
                                                iterable. Recieved output: {} \
                                                with a type of \
                                                {}'.format(output,
                                                           type(output)))
                            cmd.extend(output)
                    else:
                        output = self.tempfile.path()
                        cmd.append(output)

                        retvals = self.call(cmd, environment=environment)
                        if self.hasError(method_name, cmd, retvals):
                            if self.returnNoneOnError:
                                return None
                            else:
                                raise NCOException(**retvals)
                else:
                    if self.debug:
                        print("Use existing file: {0}".format(output))

            if returnArray:
                return self.readArray(output, returnArray)
            elif returnMaArray:
                return self.readMaArray(output, returnMaArray)
            elif self.returnCdf or returnCdf:
                if not self.returnCdf:
                    self.loadCdf()
                    return self.readCdf(output)
            else:
                return output

        if (method_name in self.__dict__) or \
           (method_name in self.operators):
            if self.debug:
                print("Found method: {0}".format(method_name))
            #cache the method for later
            setattr(self.__class__, method_name, get)
            return get.__get__(self)
        else:
            # If the method isn't in our dictionary, act normal.
            print("#=====================================================")
            print("Cannot find method: {0}".format(method_name))
            raise AttributeError("Unknown method {0}!".format(method_name))

    def loadCdf(self):
        if self.cdfMod == "scipy":
            try:
                import scipy.io.netcdf as cdf
                self.cdf = cdf
            except:
                print("Could not load scipy.io.netcdf - try to load nercdf4")
                self.cdfMod = "netcdf4"

        if self.cdfMod == "netcdf4":
            try:
                import netCDF4 as cdf
                self.cdf = cdf
            except:
                raise ImportError("scipy or python-netcdf4 module is required \
                                  to return numpy arrays.")

    def setReturnArray(self, value=True):
        self.returnCdf = value
        if value:
            self.loadCdf()

    def unsetReturnArray(self):
        self.setReturnArray(False)

    def hasNco(self, path=None):
        if path is None:
            path = self.NCOpath

        if os.path.isdir(path) and os.access(path, os.X_OK):
            return True
        else:
            return False

    def checkNco(self):
        if (self.hasNco()):
            call = [self.ncra, ' --version']
            proc = subprocess.Popen(' '.join(call),
                                    shell=True,
                                    stderr=subprocess.PIPE,
                                    stdout=subprocess.PIPE)
            retvals = proc.communicate()
            print(retvals)

    def setNco(self, value):
        self.NCOpath = value

    def getNco(self):
        return self.NCOpath

    #==================================================================
    # Addional operators:
    #------------------------------------------------------------------
    def module_version(self):
        return '0.0.0'

    def version(self):
        # return NCO's version
        proc = subprocess.Popen([self.ncra, '--version'],
                                stderr=subprocess.PIPE,
                                stdout=subprocess.PIPE)
        ret = proc.communicate()
        ncra_help = ret[1]
        match = re.search('NCO netCDF Operators version "(\d.*)" last ',
                          ncra_help)
        return match.group(1)

    def readCdf(self, infile):
        """Return a cdf handle created by the available cdf library.
        python-netcdf4 and scipy suported (default:scipy)"""
        if not self.returnCdf:
            self.loadCdf()

        if "scipy" == self.cdfMod:
            #making it compatible to older scipy versions
            fileObj = self.cdf.netcdf_file(infile, mode='r')
        elif "netcdf4" == self.cdfMod:
            fileObj = self.cdf.Dataset(infile)
        else:
            raise ImportError("Could not import data \
                              from file {0}".format(infile))
        return fileObj

    def openCdf(self, infile):
        """Return a cdf handle created by the available cdf library.
        python-netcdf4 and scipy suported (default:scipy)"""
        if not self.returnCdf:
            self.loadCdf()

        if "scipy" == self.cdfMod:
            #making it compatible to older scipy versions
            print("Use scipy")
            fileObj = self.cdf.netcdf_file(infile, mode='r+')
        elif "netcdf4" == self.cdfMod:
            print("Use netcdf4")
            fileObj = self.cdf.Dataset(infile, 'r+')
        else:
            raise ImportError("Could not import data \
                              from file: {0}".format(infile))

        return fileObj

    def readArray(self, infile, varname):
        """Direcly return a numpy array for a given variable name"""
        filehandle = self.readCdf(infile)
        if varname in filehandle.variables:
            # return the data array
            return filehandle.variables[varname][:]
        else:
            print("Cannot find variable: {0}".format(varname))
            return False

    def readMaArray(self, infile, varname):
        """Create a masked array based on cdf's FillValue"""
        fileObj = self.readCdf(infile)

        #.data is not backwards compatible to old scipy versions, [:] is
        data = fileObj.variables[varname][:]

        # load numpy if available
        try:
            import numpy as np
        except:
            raise ImportError("numpy is required to return masked arrays.")

        if hasattr(fileObj.variables[varname], '_FillValue'):
            # return masked array
            fill_val = fileObj.variables[varname]._FillValue
            retval = np.ma.masked_where(data == fill_val, data)
        else:
            #generate dummy mask which is always valid
            retval = np.ma.array(data)

        return retval


class MyTempfile(object):
    """Helper module for easy temp file handling"""
    __tempfiles = []

    def __init__(self):
        self.persistent_tempfile = False

    def __del__(self):
        # remove temporary files
        for filename in self.__class__.__tempfiles:
            if os.path.isfile(filename):
                os.remove(filename)

    def setPersist(self, value):
        self.persistent_tempfiles = value

    def path(self):
        if not self.persistent_tempfile:
            t = tempfile.NamedTemporaryFile(delete=True, prefix='ncoPy')
            self.__class__.__tempfiles.append(t.name)
            t.close()

            return t.name
        else:
            N = 10000000
            t = "{0}".format(random.randint(N))


def auto_doc(tool, nco_self):
    """Generate the __doc__ string of the decorated function by
    calling the nco help command"""
    def desc(func):
        func.__doc__ = nco_self.call([tool, '--help']).get('stdout')
        return func
    return desc


def which(pgm):
    path = os.getenv('PATH')
    for p in path.split(os.path.pathsep):
        p = os.path.join(p, pgm)
        if os.path.exists(p) and os.access(p, os.X_OK):
            return p
    return None
