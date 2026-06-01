/** Primitive formation types needed by shared/lib/algorithmParams.
 *  entities/formation re-exports these as its canonical types. */
export type FormationAlgorithm = 'probabilistic' | 'ant_colony' | 'combined';
export type FormationStatus = 'pending' | 'running' | 'completed' | 'failed';
