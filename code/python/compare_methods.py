import os
import numpy as np, pandas as pd
from itertools import product
from selection.algorithms.lasso import instance

from rules import simple_stop, forward_stop, strong_stop
from compute_pvalues import compute_pvalues, completion_index

from matplotlib import mlab

def summary(variables, pvalues, active, rule, alpha):
    """
    Compute R, V_var, V_model, screening
    for a sequence of pvalues.
    """

    completion_idx = completion_index(variables, active)
    R = rule(pvalues, alpha)
    V_var = R - len(set(active).intersection(variables[:R]))
    V_model = max(R - completion_idx, 0)
    screen = R > completion_idx
    return R, V_var, V_model, screen

def simulate(n=100, p=40, rho=0.3, snr=5,
             do_knockoff=False,
             full_results={},
             alpha=0.05,
             maxstep=np.inf,
             compute_maxT_identify=True):

    X, y, _, active, sigma = instance(n=n,
                                      p=p,
                                      rho=rho,
                                      snr=snr)
    full_results.setdefault('n', []).append(n)
    full_results.setdefault('p', []).append(p)
    full_results.setdefault('rho', []).append(rho)
    full_results.setdefault('s', []).append(len(active))
    full_results.setdefault('snr', []).append(snr)

    return run(y, X, sigma, active, 
               do_knockoff=do_knockoff,
               full_results=full_results,
               maxstep=maxstep,
               compute_maxT_identify=compute_maxT_identify)

def run(y, X, sigma, active,
        full_results={},
        do_knockoff=False,
        alpha=0.05,
        maxstep=np.inf,
        compute_maxT_identify=True):

    n, p = X.shape
    results, FS = compute_pvalues(y, X, sigma, maxstep=maxstep,
                                  compute_maxT_identify=compute_maxT_identify)
    completion_idx = completion_index(results['variable_selected'], active)
    full_results.setdefault('completion_idx', []).append(completion_idx)

    for column in results.columns:
        for i in range(results.shape[0]):
            full_results.setdefault('%s_%d' % (str(column), i+1), []).append(results[column][i])

    for i in range(len(active)):
        full_results.setdefault('active_%d' % (i+1,), []).append(active[i])

    full_results.setdefault('alpha', []).append(alpha)

    if do_knockoff:

        # this will probably not work on miller
        import rpy2.robjects as rpy
        from rpy2.robjects import numpy2ri
        rpy.conversion.py2ri = numpy2ri.numpy2ri

        numpy2ri.activate()
        rpy.r.assign('X', X)
        rpy.r.assign('y', y)

        # knockoff

        rpy.r.assign('alpha', alpha)
        knockoff = np.array(rpy.r("""
        library(knockoff)
        knockoff.filter(X = X, y = y, fdr=alpha)$selected
    """)) - 1
        numpy2ri.deactivate()
        knockoff_R = knockoff.shape[0]
        knockoff_V = knockoff_R - len(set(active).intersection(knockoff))
        knockoff_screen = knockoff_R > completion_idx
        full_results.setdefault('knockoff_R', []).append(knockoff_R)
        full_results.setdefault('knockoff_V', []).append(knockoff_V)
        full_results.setdefault('knockoff_screen', []).append(knockoff_screen)

    for pval, rule_ in product(['maxT_identify_pvalue',
                                'saturated_pvalue',
                                'nominal_pvalue',
                                'maxT_pvalue'],
                               zip([simple_stop, 
                                    strong_stop,
                                    forward_stop],
                                   ['simple',
                                    'strong',
                                    'forward'])):
        rule, rule_name = rule_
        R, V_var, V_model, screen = summary(results['variable_selected'],
                                            results[pval],
                                            active,
                                            rule, 
                                            alpha)
        pval_name = pval.split('_')[0]
        full_results.setdefault('%s_%s_R' % (pval_name, rule_name), []).append(R)
        full_results.setdefault('%s_%s_V_var' % (pval_name, rule_name), []).append(V_var)
        full_results.setdefault('%s_%s_V_model' % (pval_name, rule_name), []).append(V_model)
        full_results.setdefault('%s_%s_screen' % (pval_name, rule_name), []).append(screen)

    return full_results, FS

def batch(outbase, nsim, **simulate_args):

    full_results = {}
    simulate_args['full_results'] = full_results
    for i in range(nsim):
        try:
            print 'run %d' % (i+1)
            simulate(**simulate_args)
            df = pd.DataFrame(full_results)
            df.to_csv(outbase + '.csv', index=False)
        except:
            pass

if __name__ == "__main__":
    from argparse import ArgumentParser
    parser = ArgumentParser(
        description= '''
Run a batch of simulations.
        ''')
    parser.add_argument('--nsim',
                        help='How many simulations to run.', type=int)
    parser.add_argument('--outbase',
                        help='Where to store results')
    args = parser.parse_args()
    batch(args.outbase, args.nsim, do_knockoff=True)