#!/usr/bin/env python
# 06.04.2005, c 
# 16.06.2005
import os.path as op
from optparse import OptionParser

import init_sfepy
from sfepy.base.base import *
from sfepy.base.conf import ProblemConf
from sfepy.fem.evaluate import BasicEvaluator
from sfepy.solvers.nls import Newton
from sfepy.solvers.oseen import Oseen
from sfepy.solvers.ls import Umfpack
from sfepy.solvers.generic import solve_stationary
import sfepy.base.ioutils as io
#import sfepy.optimize.fluentutils as fluu
import sfepy.optimize.shapeOptim as so
from sfepy.fem.problemDef import ProblemDefinition
from sfepy.solvers import Solver
from sfepy.fem.variables import zero_conf_ebc

##
# 11.10.2007, c
# 17.10.2007
def solve_stokes( dpb, equations_stokes, nls_conf ):
    dpb.set_equations( equations_stokes )
    dpb.time_update( None )
    output( 'Stokes...' )
    return dpb.solve( nls_conf = nls_conf )

##
# 22.11.2006, c
# 23.11.2006
# 20.03.2007
# 26.07.2007
# 11.10.2007
# 17.10.2007
def solve_navier_stokes( conf, options ):
    opts = conf.options

    dpb = ProblemDefinition.from_conf( conf, init_equations = False )
    equations = getattr( conf, '_'.join( ('equations_direct', opts.problem) ) )

    dpb.set_equations( equations )

    ls_conf = dpb.get_solver_conf( opts.ls )
    nls_conf = dpb.get_solver_conf( opts.nls_direct )

    ls = Solver.any_from_conf( ls_conf )

    method = opts.direct_method
    if method == 'stationary':
        data = {}
        dpb.time_update( None )
        ev = BasicEvaluator( dpb, data = data )

        vec_dp0 = dpb.create_state_vector()
        dpb.apply_ebc( vec_dp0 )
        nls = Solver.any_from_conf( nls_conf, evaluator = ev, lin_solver = ls )
        vec_dp = nls( vec_dp0 )

    elif method == 'transient':
        ts_conf = dpb.get_solver_conf( opts.ts_direct )

        data = {'ts' : Struct( dt = ts_conf.dt )}

        # Plug in mass term.
        mequations = {}
        for key, eq in equations.iteritems():
            if 'dw_div_grad' in eq:
                eq = '+'.join( (ts_conf.mass_term, eq) ).replace( '++', '+')
            mequations[key] = eq

        if ts_conf.stokes_init:
            vec_dp0 = solve_stokes( dpb, conf.equations_direct_stokes, nls_conf )
            dpb.set_equations( mequations )
        else:
            dpb.set_equations( mequations )
            vec_dp0 = dpb.create_state_vector()
            dpb.time_update( None )
            dpb.apply_ebc( vec_dp0 )

        from sfepy.base.log import Log

        log = Log.from_conf( Struct( is_plot = True ),
                            ([r'$||u||$'], [r'$||p||$']) )

        output( 'Navier-Stokes...' )
        ev = BasicEvaluator( dpb, ts = Struct( dt = ts_conf.dt ) )
        nls = Solver.any_from_conf( nls_conf, evaluator = ev, lin_solver = ls )

        n_step = ts_conf.n_step
        step = 0
        while 1:
            for ii in xrange( n_step ):
                output( step )

                vec_u = dpb.variables.get_state_part_view( vec_dp0, 'w' )
                vec_p = dpb.variables.get_state_part_view( vec_dp0, 'r' )
                log( nm.linalg.norm( vec_u ), nm.linalg.norm( vec_p ) )

                dpb.variables.non_state_data_from_state( 'w_0', vec_dp0, 'w' )
                vec_dp = nls( vec_dp0 )

                step += 1
                vec_dp0 = vec_dp.copy()

            if ts_conf.interactive:
                try:
                    n_step = int( raw_input( 'continue: ' ) )
                    if n_step <= 0: break
                except:
                    break

        vec_u = dpb.variables.get_state_part_view( vec_dp, 'w' )
        vec_p = dpb.variables.get_state_part_view( vec_dp, 'r' )
        log( nm.linalg.norm( vec_u ), nm.linalg.norm( vec_p ), finished = True )

    else:
        raise 'unknown Navier-Stokes solution method (%s)!'  % method
    
    return dpb, vec_dp, data

##
# 01.11.2007, c
def solve_generic_direct( conf, options ):
    opts = conf.options

    dpb = ProblemDefinition.from_conf( conf, init_equations = False )
    equations = getattr( conf,
                         '_'.join( ('equations_direct', opts.problem) ) )
    dpb.set_equations( equations )

    ls_conf = dpb.get_solver_conf( opts.ls )
    nls_conf = dpb.get_solver_conf( opts.nls_direct )

    ls = Solver.any_from_conf( ls_conf )

    data = {}
    dpb.time_update( None )
    ev = BasicEvaluator( dpb, data = data )

    vec_dp0 = dpb.create_state_vector()
    dpb.apply_ebc( vec_dp0 )

    nls = Solver.any_from_conf( nls_conf, evaluator = ev, lin_solver = ls )
    vec_dp = nls( vec_dp0 )
##     pause()
##     vec_dp[dpb.variables.get_indx( 'r' )] += 100.0
##     vec_dp = nls( vec_dp )
##     pause()
    return dpb, vec_dp, data

##
# c: 22.11.2006, r: 15.04.2008
def solve_direct( conf, options ):
    opts = conf.options
    if hasattr( opts, 'problem' ):
        if opts.problem == 'navier_stokes':
            dpb, vec_dp, data = solve_navier_stokes( conf, options )
        else:
            output( 'unknown problem type (%s), using generic solver.'\
                    % opts.problem )
            dpb, vec_dp, data = solve_generic_direct( conf, options )
    else: # Generic direct problem.
        dpb, vec_dp, data = solve_generic_direct( conf, options )

    trunk = io.get_trunk( conf.filename_mesh )
    dpb.save_state( trunk + '_direct.vtk', vec_dp )

##     print dpb.materials['stabil']
##     pause()
    if options.dump_filename is not None:
        import tables as pt
        import numarray as nar

        fd = pt.openFile( options.dump_filename, mode = 'w',
                          title = "Dump file" )
        for key, val in out.iteritems():
            fd.createArray( fd.root, key, nar.asarray( val.data ), 
                            '%s data' % val.mode )
        fd.close()

    if options.pert_mesh_filename is not None:
        coors0 = dpb.get_mesh_coors()
        # !!!
        # 'u' is here for displacements of le.py!
        vec_u = dpb.variables.get_state_part_view( vec_dp, 'u' ).copy()
        vec_u = vec_u.reshape( coors0.shape )
        coors = coors0 + vec_u
        dpb.set_mesh_coors( coors )
        dpb.domain.mesh.write( options.pert_mesh_filename, io = 'auto' )

    return dpb, vec_dp, data

##
# c: 01.11.2007, r: 15.04.2008
def solve_generic_adjoint( conf, options, dpb, vec_dp, data ):
    opts = conf.options

    if dpb:
        apb = dpb.copy( share = ['domain', 'conf', 'fields',
                                 'materials', 'mtx_a', 'solvers'] )
        ebc = zero_conf_ebc( conf.ebcs )
        apb.set_variables( conf.variables ) 
    else:
        ebc = conf.ebcs = zero_conf_ebc( conf.ebcs )
        apb = ProblemDefinition.from_conf( conf )

    equations = getattr( conf, '_'.join( ('equations_adjoint',
                                          opts.problem,
                                          opts.objective_function) ) )
    apb.set_equations( equations )
    apb.time_update( None, conf_ebc = ebc )

    vec_ap = apb.create_state_vector()
    apb.apply_ebc( vec_ap )

    so.set_state_to_vars( apb.variables, opts.var_map, vec_dp )

    ls_conf = apb.get_solver_conf( opts.ls )
    nls_conf = apb.get_solver_conf( opts.nls_adjoint )

    ls = Solver.any_from_conf( ls_conf )

    ev = BasicEvaluator( apb, data = data )
    nls = Solver.any_from_conf( nls_conf, evaluator = ev, lin_solver = ls )

    vec_ap = nls( vec_ap )

    trunk = io.get_trunk( conf.filename_mesh )
    apb.save_state( trunk + '_adjoint.vtk', vec_ap )

    shape_opt = so.ShapeOptimFlowCase.from_conf( conf, apb.domain )
##     print shape_opt
##     pause()

    if options.test is not None:
        ##
        # Test shape sensitivity.
        if shape_opt.test_terms_if_test:
            so.test_terms( [options.test], opts.term_delta, shape_opt,
                           vec_dp, vec_ap, apb )

        dev = BasicEvaluator( dpb, data = data )
        dnls_conf = apb.get_solver_conf( opts.nls_direct )
        dnls = Solver.any_from_conf( dnls_conf, evaluator = dev, lin_solver = ls )
        shape_opt.check_sensitivity( [options.test], opts.delta, vec_dp, vec_ap,
                                   dnls, apb.conf,
                                   apb.domain, apb.variables,
                                   apb.materials, data )
    ##
    # Compute objective function.
    val = shape_opt.obj_fun( vec_dp, apb.conf, apb.domain,
                           apb.variables, apb.materials, data = data )
    print 'actual obj_fun:', val
##         pause()

    ##
    # Compute shape sensitivity.
    vec_sa = shape_opt.sensitivity( vec_dp, vec_ap, apb.conf, apb.domain,
                                  apb.variables, apb.materials,
                                  data = data )
    print 'actual sensitivity:', vec_sa

##
# c: 22.11.2006, r: 15.04.2008
def solve_navier_stokes_adjoint( conf, options, dpb, vec_dp, data ):
    opts = conf.options

    if dpb:
        apb = dpb.copy( share = ['domain', 'conf', 'fields',
                                 'materials', 'mtx_a', 'solvers'] )
        ebc = zero_conf_ebc( conf.ebcs )
        apb.set_variables( conf.variables ) 
    else:
        ebc = conf.ebcs = zero_conf_ebc( conf.ebcs )
        apb = ProblemDefinition.from_conf( conf )

    equations = getattr( conf, '_'.join( ('equations_adjoint',
                                          opts.problem,
                                          opts.objective_function) ) )

    apb.set_equations( equations )

    extra_mat_args = {}
    fixed_data = None
    aux_conf = apb.get_solver_conf( opts.nls_direct )
    if hasattr( aux_conf, 'stabil_mat_name' ):
        st_name = aux_conf.stabil_mat_name
        if apb.materials.has_key( st_name ):
            mat = apb.materials[st_name]
            fixed_data = copy( mat.datas )
            vec_b = vec_dp[dpb.variables.get_indx( 'w' )]
            b_norm = nla.norm( vec_b, nm.inf )
            extra_mat_args = {st_name : {'b_norm' : b_norm, 'fixed_data' : fixed_data}}
            
    apb.time_update( None, conf_ebc = ebc, extra_mat_args = extra_mat_args )

    indx = dpb.variables.get_indx( 'r' )
    vec_dp[indx,nm.newaxis].tofile( 'p_p.txt', ' ' )

    is_pressure = 'r' in apb.variables.names
    if not options.direct:
        vec_u, vec_p = fluu.read_state( conf, apb.fields, 1 )

        # For objective funstion...
        vec_dp = apb.create_state_vector()
        apb.variables.set_state_part( vec_dp, vec_u.ravel(), 'w' )
        if is_pressure:
            apb.variables.set_state_part( vec_dp, vec_p, 'r' )

    vec_ap = apb.create_state_vector()
    apb.apply_ebc( vec_ap )

    so.set_state_to_vars( apb.variables, opts.var_map, vec_dp )

    ls_conf = apb.get_solver_conf( opts.ls )
    nls_conf = apb.get_solver_conf( opts.nls_adjoint )

    ls = Solver.any_from_conf( ls_conf )

    ev = BasicEvaluator( apb, data = data )
    if nls_conf.kind == 'nls.oseen':
        nls_conf.fixed_data = fixed_data
    nls = Solver.any_from_conf( nls_conf, evaluator = ev, lin_solver = ls )

    vec_ap = nls( vec_ap )

    indx = apb.variables.get_indx( 'r' )
    vec_ap[indx,nm.newaxis].tofile( 'p_r.txt', ' ' )

    trunk = io.get_trunk( conf.filename_mesh )
    apb.save_state( trunk + '_adjoint.vtk', vec_ap )

    shape_opt = so.ShapeOptimFlowCase.from_conf( conf, apb.domain )
##     print shape_opt
##     pause()

    if options.test is not None:
        ##
        # Test shape sensitivity.
        if shape_opt.test_terms_if_test:
            so.test_terms( [options.test], opts.term_delta, shape_opt,
                           vec_dp, vec_ap, apb )

        dev = BasicEvaluator( dpb, data = data )
        dnls_conf = apb.get_solver_conf( opts.nls_direct )
        if dnls_conf.kind == 'nls.oseen':
            dnls_conf.fixed_data = fixed_data
        dnls = Solver.any_from_conf( dnls_conf, evaluator = dev, lin_solver = ls )
        shape_opt.check_sensitivity( [options.test], opts.delta, vec_dp, vec_ap,
                                   dnls, apb.conf,
                                   apb.domain, apb.variables,
                                   apb.materials, data )
    ##
    # Compute objective function.
    val = shape_opt.obj_fun( vec_dp, apb.conf, apb.domain,
                           apb.variables, apb.materials, data = data )
    print 'actual obj_fun:', val
##         pause()

    ##
    # Compute shape sensitivity.
    vec_sa = shape_opt.sensitivity( vec_dp, vec_ap, apb.conf, apb.domain,
                                  apb.variables, apb.materials,
                                  data = data )
    print 'actual sensitivity:', vec_sa

##         pylab.plot( vec_sa )
##         pylab.show()

##
# 01.11.2007, c
def solve_adjoint( conf, options, dpb, vec_dp, data ):
    opts = conf.options
    if hasattr( opts, 'problem' ):
        if opts.problem == 'navier_stokes':
            solve_navier_stokes_adjoint( conf, options, dpb, vec_dp, data )
        else:
            output( 'unknown problem type (%s), using generic solver.'\
                    % opts.problem )
            solve_generic_adjoint( conf, options, dpb, vec_dp, data )
    else: # Generic direct problem.
        solve_generic_adjoint( conf, options, dpb, vec_dp, data )

##
# c: 22.11.2006, r: 15.04.2008
def solve_optimize( conf, options ):
    opts = conf.options
    trunk = io.get_trunk( conf.filename_mesh )
    data = {}

    dpb = ProblemDefinition.from_conf( conf, init_equations = False )
    equations = getattr( conf, '_'.join( ('equations_direct', opts.problem) ) )

    dpb.set_equations( equations )

    dpb.name = 'direct'
    dpb.time_update( None )

    apb = dpb.copy( share = ['domain', 'conf', 'fields',
                             'materials', 'mtx_a', 'solvers'] )
    ebc = zero_conf_ebc( conf.ebcs )
    apb.set_variables( conf.variables ) 

    equations = getattr( conf, '_'.join( ('equations_adjoint',
                                          opts.problem,
                                          opts.objective_function) ) )

    apb.set_equations( equations )
    apb.name = 'adjoint'
    apb.time_update( None, conf_ebc = ebc )

    ls_conf = apb.get_solver_conf( opts.ls )
    dnls_conf = apb.get_solver_conf( opts.nls_direct )
    anls_conf = apb.get_solver_conf( opts.nls_adjoint )
    opt_conf = apb.get_solver_conf( opts.optimizer )

    ls = Solver.any_from_conf( ls_conf )

    ev = BasicEvaluator( dpb, data = data )
    dnls = Solver.any_from_conf( dnls_conf, evaluator = ev, lin_solver = ls )

    ev = BasicEvaluator( apb, data = data )
    anls = Solver.any_from_conf( anls_conf, evaluator = ev, lin_solver = ls )

    shape_opt = so.ShapeOptimFlowCase.from_conf( conf, apb.domain )
    design0 = shape_opt.dsg_vars.val
    shape_opt.cache = Struct( design = design0 + 100,
                             vec_dp = None,
                             i_mesh = -1 )

    opt_status = IndexedStruct()
    optimizer = Solver.any_from_conf( opt_conf,
                                    obj_fun = so.obj_fun,
                                    obj_fun_grad = so.obj_fun_grad,
                                    status = opt_status,
                                    obj_args = (shape_opt, dpb, apb,
                                               dnls, anls, opts) )


    ##
    # State problem solution for the initial design.
    vec_dp0 = so.solve_problem_for_design( design0, shape_opt, dnls, opts )

    dpb.save_state( trunk + '_direct_initial.vtk', vec_dp0 )

    ##
    # Optimize.
    des = optimizer( design0 )
    print opt_status

    ##
    # Save final state (for "optimal" design).
    dpb.domain.mesh.write( trunk + '_opt.mesh', io = 'auto' )
    dpb.save_state( trunk + '_direct_current.vtk', shape_opt.cache.vec )

    print des

usage = """%prog [options] filename_in"""

help = {
    'server_mode' :
    "run in server mode [default: %default], N/A",
    'adjoint' :
    "solve adjoint problem [default: %default]",
    'direct' :
    "solve direct problem [default: %default]",
    'test' :
    "test sensitivity by finite difference,"
    " using design variable idsg; switches on -a, -d",
    'dump' :
    "dump direct problem state to filename",
    'pert':
    "save displacement-perturbed mesh to filename",
    'optimize' :
    "full shape optimization problem",
}

##
# created:       13.06.2005
# last revision: 15.04.2008
def main():
    version = open( op.join( init_sfepy.install_dir,
                             'VERSION' ) ).readlines()[0][:-1]

    parser = OptionParser( usage = usage, version = "%prog " + version )
    parser.add_option( "-s", "--server",
                       action = "store_true", dest = "server_mode",
                       default = False, help = help['server_mode'] )
    parser.add_option( "-a", "--adjoint",
                       action = "store_true", dest = "adjoint",
                       default = False, help = help['adjoint'] )
    parser.add_option( "-d", "--direct",
                       action = "store_true", dest = "direct",
                       default = False, help = help['direct'] )
    parser.add_option( "-t", "--test", type = int, metavar = 'idsg',
                       action = "store", dest = "test",
                       default = None, help = help['test'] )
    parser.add_option( "", "--dump", metavar = 'filename',
                       action = "store", dest = "dump_filename",
                       default = None, help = help['dump'] )
    parser.add_option( "", "--pert-mesh", metavar = 'filename',
                       action = "store", dest = "pert_mesh_filename",
                       default = None, help = help['pert'] )
    parser.add_option( "-f", "--full",
                       action = "store_true", dest = "optimize",
                       default = False, help = help['optimize'] )

    options, args = parser.parse_args()
#    print options; pause()
    
    if options.test is not None:
        options.adjoint = options.direct = True

    if options.optimize:
        options.adjoint = options.direct = False

    if ((len( args ) == 1)
        and (options.direct or options.adjoint or options.optimize)):
        filename_in = args[0];
    else:
        parser.print_help(),
        return

    required = ['filename_mesh', 'field_[0-9]+', 'ebc|nbc', 'fe',
                'region_[0-9]+', 'variables', 'material_[0-9]+',
                'solver_[0-9]+', 'integral_[0-9]+']
    other = ['functions', 'modules', 'epbc', 'lcbc', 'problem', 'options']
    if options.adjoint:
        required += ['equations_adjoint_.*', 'filename_vp']
        if options.direct:
            required += ['equations_direct_.*']
    elif options.direct:
        required += ['equations_direct_.*']
    elif options.optimize:
        required += ['equations_direct_.*', 'equations_adjoint_.*',
                     'equations_sensitivity_.*',
                     'filename_vp']
        
    conf = ProblemConf.from_file( filename_in, required, other )
##     print conf
##     pause()

    if options.direct:
        dpb, vec_dp, data = solve_direct( conf, options )
    else:
        dpb, vec_dp, data = None, None, None
        
    if options.adjoint:
        solve_adjoint( conf, options, dpb, vec_dp, data )

    if options.optimize:
        solve_optimize( conf, options )

if __name__ == '__main__':
    main()

##     import profile
##     import pstats

##     profile.run( 'main()', 'prof.dat' )
##     p = pstats.Stats( 'prof.dat' ).strip_dirs()

##     p.print_callers()

##     import trace, coverage

##     trace = trace.Trace(ignoredirs=[sys.prefix, sys.exec_prefix,], trace = 1,
##                         count = 1 )
##     # run the new command using the given trace
##     trace.run( coverage.globaltrace, 'main()' )
##     # make a report, telling it where you want output
##     r = trace.results()
##     r.write_results( show_missing = True )

##     import sfepy.ib.ccore.sort_rows as sort_rows
##     aux = nm.arange( 12, dtype = nm.int32 )
##     aux.shape = (4,3)
##     aux[0,2] = 9
##     aux[2,1] = 1
##     aux[1,2] = 20
##     print aux
##     sort_rows.sort_rows( aux, nm.array( [1,2], nm.int32 ) )
##     print aux
    