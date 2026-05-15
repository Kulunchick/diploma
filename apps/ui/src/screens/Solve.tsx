import {Card, CardHeader, CardTitle, CardContent} from "@/components/ui/card.tsx"
import {Input} from "@/components/ui/input.tsx"
import {ValidatedInput} from "@/components/ui/validated-input.tsx"
import {Button} from "@/components/ui/button.tsx"
import {useMemo, useState} from "react"

import {Matrix} from "@/components/Matrix.tsx";
import {Chart} from "@/components/Chart.tsx";
import {useJobStream} from "@/hooks/useJobStream";
import type {SolveResult} from "@/api/types";

interface AlgorithmParameters {
    ant_colony: {
        Kmax: number;
        num_ants: number;
        alpha: number;
        beta: number;
        p: number;
        tau: number;
    };
    probabilistic: {
        Kmax: number;
    };
}

interface WebSocketData {
    m: number;
    n: number;
    c: number[][];
    B_ij: number[][];
    B_total: number;
    omega: number[][];
    algorithm_parameters: AlgorithmParameters;
}

export default function Solve() {
    const createMatrix = (rows: number = 3, cols: number = 3, value: number = 1) =>
        Array(rows).fill(value).map(() => Array(cols).fill(value));
    const [priceMatrix, setPriceMatrix] = useState<number[][]>(createMatrix(3, 3));
    const [resourceMatrix, setResourceMatrix] = useState<number[][]>(createMatrix(3, 3));
    const [discountMatrix, setDiscountMatrix] = useState<number[][]>(createMatrix(3, 3, 0));
    const [totalResource, setTotalResource] = useState<number>(16000);

    const [priceMinMax, setPriceMinMax] = useState({ min: 100, max: 1000 });
    const [resourceMinMax, setResourceMinMax] = useState({ min: 1000, max: 5000 });
    const [discountMinMax, setDiscountMinMax] = useState({ min: 0, max: 1 });

    const generateRandomNumber = (min: number, max: number): number => {
        return Math.floor(Math.random() * (max - min + 1)) + min;
    };

    const generateRandomDecimal = (min: number, max: number): number => {
        return Number((Math.random() * (max - min) + min).toFixed(2));
    };

    const randomizeMatrix = (matrix: number[][], min: number, max: number, isDecimal: boolean = false): number[][] => {
        return matrix.map(row =>
            row.map(() => isDecimal ? generateRandomDecimal(min, max) : generateRandomNumber(min, max))
        );
    };

    const [antColonyParams, setAntColonyParams] = useState({
        Kmax: 100,
        num_ants: 20,
        alpha: 1,
        beta: 2,
        p: 0.1,
        tau: 1,
    });
    const [probabilisticParams, setProbabilisticParams] = useState({
        Kmax: 100
    });

    const [columnLabels, setColumnLabels] = useState<string[]>(["Company 1", "Company 2", "Company 3"])
    const [rowLabels, setRowLabels] = useState<string[]>(["Technic 1", "Technic 2", "Technic 3"])
    const [newColumnLabel, setNewColumnLabel] = useState("")
    const [newRowLabel, setNewRowLabel] = useState("")

    const addColumn = () => {
        setPriceMatrix(prev => prev.map(row => [...row, 0]))
        setResourceMatrix(prev => prev.map(row => [...row, 0]))
        setDiscountMatrix(prev => prev.map(row => [...row, 0]))
        setColumnLabels(prev => [...prev, newColumnLabel || `Company ${prev.length + 1}`])
        setNewColumnLabel("")
    }

    const addRow = () => {
        setPriceMatrix(prev => [...prev, Array(prev[0]?.length || 0).fill(0)])
        setResourceMatrix(prev => [...prev, Array(prev[0]?.length || 0).fill(0)])
        setDiscountMatrix(prev => [...prev, Array(prev[0]?.length || 0).fill(0)])
        setRowLabels(prev => [...prev, newRowLabel || `Technic ${prev.length + 1}`])
        setNewRowLabel("")
    }

    const removeColumn = (colIndex: number) => {
        setPriceMatrix(prev => prev.map(row => row.filter((_, index) => index !== colIndex)));
        setResourceMatrix(prev => prev.map(row => row.filter((_, index) => index !== colIndex)));
        setDiscountMatrix(prev => prev.map(row => row.filter((_, index) => index !== colIndex)));
    };

    const removeRow = (rowIndex: number) => {
        setPriceMatrix(prev => prev.filter((_, index) => index !== rowIndex));
        setResourceMatrix(prev => prev.filter((_, index) => index !== rowIndex));
        setDiscountMatrix(prev => prev.filter((_, index) => index !== rowIndex));
    };

    const stream = useJobStream<SolveResult>({ streamMessages: true });

    const chartData = useMemo(() => {
        const data: Array<{ iteration: number; aco: number; prob: number }> = [];
        for (const msg of stream.messages) {
            if (msg.type !== 'iteration') continue;
            const existing = data.find(p => p.iteration === msg.iteration);
            if (existing) {
                if (msg.algorithm === 'ant_colony') existing.aco = Math.round(msg.current_best_value);
                else existing.prob = Math.round(msg.current_best_value);
            } else {
                const last = data[data.length - 1] ?? { aco: 0, prob: 0 };
                data.push({
                    iteration: msg.iteration,
                    aco: msg.algorithm === 'ant_colony' ? Math.round(msg.current_best_value) : last.aco,
                    prob: msg.algorithm === 'probabilistic' ? Math.round(msg.current_best_value) : last.prob,
                });
            }
        }
        return data;
    }, [stream.messages]);

    const m = priceMatrix.length;
    const n = priceMatrix[0]?.length ?? 3;
    const probSolution = stream.result?.probabilistic?.solution ?? createMatrix(m, n, 0);
    const antSolution  = stream.result?.ant_colony?.solution  ?? createMatrix(m, n, 0);
    const probValue    = stream.result?.probabilistic?.value  ?? 0;
    const antValue     = stream.result?.ant_colony?.value     ?? 0;

    const handleSolve = () => {
        const data: WebSocketData = {
            m: resourceMatrix.length,
            n: resourceMatrix[0].length,
            c: priceMatrix,
            B_ij: resourceMatrix,
            B_total: totalResource,
            omega: discountMatrix,
            algorithm_parameters: {
                ant_colony: antColonyParams,
                probabilistic: probabilisticParams
            }
        };
        void stream.start('/solve', data);
    };

    return (
        <div className="flex flex-col gap-4">
            <div className="mt-4 flex justify-between">
                <div className=" flex flex-col gap-2 min-w-xl">
                    <div className="flex gap-2 items-center">
                        <Input type="text" id="x" placeholder="Company" value={newColumnLabel}
                               onChange={e => setNewColumnLabel(e.target.value)}/>
                        <div className="flex justify-end">
                            <Button onClick={addColumn} className="min-w-40">Додати компанію</Button>
                        </div>
                    </div>
                    <div className="flex gap-2 items-center">
                        <Input type="text" id="y" placeholder="Technics" value={newRowLabel}
                               onChange={e => setNewRowLabel(e.target.value)}/>
                        <div className="flex justify-end">
                            <Button onClick={addRow} className="min-w-40">Додати обладнання</Button>
                        </div>
                    </div>
                </div>
            </div>

            <Card className="w-full overflow-auto">
                <CardHeader>
                    <CardTitle>Матриця Цін</CardTitle>
                </CardHeader>
                <CardContent>
                    <Matrix
                        matrix={priceMatrix}
                        setMatrix={setPriceMatrix}
                        columnLabels={columnLabels}
                        setColumnLabels={setColumnLabels}
                        rowLabels={rowLabels}
                        setRowLabels={setRowLabels}
                        onRemoveColumn={removeColumn}
                        onRemoveRow={removeRow}
                        min={0}
                        step={100}
                        isInteger={true}
                    />
                </CardContent>
                <div className="mx-6 my-5 max-w-sm flex gap-2">
                    <div className="flex gap-2 items-center max-w-30">
                        <ValidatedInput
                            type="number"
                            value={priceMinMax.min}
                            onChange={(value) => setPriceMinMax(prev => ({...prev, min: Number(value)}))}
                            placeholder="Min"
                            min={0}
                            step={100}
                            max={priceMinMax.max}
                            isInteger={true}
                        />
                    </div>
                    <div className="flex gap-2 items-center max-w-30">
                        <ValidatedInput
                            type="number"
                            value={priceMinMax.max}
                            onChange={(value) => setPriceMinMax(prev => ({...prev, max: Number(value)}))}
                            placeholder="Max"
                            min={priceMinMax.min}
                            step={100}
                            isInteger={true}
                        />
                    </div>
                    <div className="flex justify-end">
                        <Button
                            onClick={() => {
                                const newMatrix = randomizeMatrix(priceMatrix, priceMinMax.min, priceMinMax.max);
                                setPriceMatrix(newMatrix);
                            }}
                        >
                            Randomize
                        </Button>
                    </div>
                </div>
            </Card>

            <Card className="w-full overflow-auto">
                <CardHeader>
                    <CardTitle>Матриця Технічного Ресурсу</CardTitle>
                </CardHeader>
                <CardContent>
                    <Matrix
                        matrix={resourceMatrix}
                        setMatrix={setResourceMatrix}
                        columnLabels={columnLabels}
                        setColumnLabels={setColumnLabels}
                        rowLabels={rowLabels}
                        setRowLabels={setRowLabels}
                        onRemoveColumn={removeColumn}
                        onRemoveRow={removeRow}
                        min={0}
                        step={100}
                        isInteger={true}
                    />
                    <div className="mt-4">
                        <ValidatedInput
                            type="number"
                            value={totalResource}
                            onChange={(value) => setTotalResource(Number(value))}
                            placeholder="Загальний ресурс"
                            min={0}
                            step={100}
                            isInteger={true}
                        />
                    </div>
                </CardContent>
                <div className="mx-6 my-5 max-w-sm flex gap-2">
                    <div className="flex gap-2 items-center max-w-30">
                        <ValidatedInput
                            type="number"
                            value={resourceMinMax.min}
                            onChange={(value) => setResourceMinMax(prev => ({...prev, min: Number(value)}))}
                            placeholder="Min"
                            min={0}
                            step={100}
                            max={resourceMinMax.max}
                            isInteger={true}
                        />
                    </div>
                    <div className="flex gap-2 items-center max-w-30">
                        <ValidatedInput
                            type="number"
                            value={resourceMinMax.max}
                            onChange={(value) => setResourceMinMax(prev => ({...prev, max: Number(value)}))}
                            placeholder="Max"
                            min={resourceMinMax.min}
                            step={100}
                            isInteger={true}
                        />
                    </div>
                    <div className="flex justify-end">
                        <Button
                            onClick={() => {
                                const newMatrix = randomizeMatrix(resourceMatrix, resourceMinMax.min, resourceMinMax.max);
                                setResourceMatrix(newMatrix);
                                const totalSum = newMatrix.reduce((sum, row) =>
                                    sum + row.reduce((rowSum, cell) => rowSum + cell, 0), 0);
                                const minValue = Math.min(...newMatrix.flat());
                                setTotalResource(generateRandomNumber(minValue, totalSum));
                            }}
                        >
                            Randomize
                        </Button>
                    </div>
                </div>
            </Card>

            <Card className="w-full overflow-auto">
                <CardHeader>
                    <CardTitle>Матриця Знижок</CardTitle>
                </CardHeader>
                <CardContent>
                    <Matrix
                        matrix={discountMatrix}
                        setMatrix={setDiscountMatrix}
                        columnLabels={columnLabels}
                        setColumnLabels={setColumnLabels}
                        rowLabels={rowLabels}
                        setRowLabels={setRowLabels}
                        onRemoveColumn={removeColumn}
                        onRemoveRow={removeRow}
                        min={0}
                        max={1}
                        step={0.1}
                    />
                </CardContent>
                <div className="mx-6 my-5 max-w-sm flex gap-2">
                    <div className="flex gap-2 items-center max-w-30">
                        <ValidatedInput
                            type="number"
                            value={discountMinMax.min}
                            onChange={(value) => setDiscountMinMax(prev => ({...prev, min: Number(value)}))}
                            placeholder="Min"
                            step={0.1}
                            min={0}
                            max={discountMinMax.max}
                        />
                    </div>
                    <div className="flex gap-2 items-center max-w-30">
                        <ValidatedInput
                            type="number"
                            value={discountMinMax.max}
                            onChange={(value) => setDiscountMinMax(prev => ({...prev, max: Number(value)}))}
                            placeholder="Max"
                            step={0.1}
                            min={discountMinMax.min}
                            max={1}
                        />
                    </div>
                    <div className="flex justify-end">
                        <Button
                            onClick={() => setDiscountMatrix(randomizeMatrix(discountMatrix, discountMinMax.min, discountMinMax.max, true))}
                        >
                            Randomize
                        </Button>
                    </div>
                </div>
            </Card>

            <Card className="w-full overflow-auto">
                <CardHeader>
                    <CardTitle>Ймовірнісний алгоритм</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="max-w-sm flex gap-2">
                        <div className="flex gap-2 items-center max-w-30">
                            <label className="text-gray-500 text-[14px]">Kmax</label>
                            <ValidatedInput
                                type="number"
                                value={probabilisticParams.Kmax}
                                onChange={(value) => setProbabilisticParams({
                                    Kmax: Number(value)
                                })}
                                placeholder="Kmax"
                                min={1}
                                step={1}
                                isInteger={true}
                            />
                        </div>
                    </div>
                </CardContent>
            </Card>

            <Card className="w-full overflow-auto">
                <CardHeader>
                    <CardTitle>Алгоритм мурашиних колоній</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="max-w-2xl flex gap-2">
                        <div className="flex gap-2 items-center max-w-30">
                        <label className="text-gray-500 text-[14px]">Kmax:</label>
                            <ValidatedInput
                                type="number"
                                value={antColonyParams.Kmax}
                                onChange={(value) => setAntColonyParams(prev => ({
                                    ...prev,
                                    Kmax: Number(value)
                                }))}
                                placeholder="Kmax"
                                min={1}
                                step={1}
                                isInteger={true}
                            />
                        </div>
                        <div className="flex gap-2 items-center max-w-30">
                        <label className="text-gray-500 text-[14px]">L:</label>
                            <ValidatedInput
                                type="number"
                                value={antColonyParams.num_ants}
                                onChange={(value) => setAntColonyParams(prev => ({
                                    ...prev,
                                    num_ants: Number(value)
                                }))}
                                placeholder="Кількість мурах"
                                min={1}
                                step={1}
                                isInteger={true}
                            />
                        </div>
                        <div className="flex gap-2 items-center max-w-30">
                        <label className="text-gray-500 text-[14px]">α:</label>
                            <ValidatedInput
                                type="number"
                                value={antColonyParams.alpha}
                                onChange={(value) => setAntColonyParams(prev => ({
                                    ...prev,
                                    alpha: Number(value)
                                }))}
                                placeholder="Альфа"
                                min={0}
                                step={0.1}
                            />
                        </div>
                        <div className="flex gap-2 items-center max-w-30">
                        <label className="text-gray-500 text-[14px]">β:</label>
                            <ValidatedInput
                                type="number"
                                value={antColonyParams.beta}
                                onChange={(value) => setAntColonyParams(prev => ({
                                    ...prev,
                                    beta: Number(value)
                                }))}
                                placeholder="Бета"
                                min={0}
                                step={0.1}
                            />
                        </div>
                        <div className="flex gap-2 items-center max-w-30">
                        <label className="text-gray-500 text-[14px]">p:</label>
                            <ValidatedInput
                                type="number"
                                value={antColonyParams.p}
                                onChange={(value) => setAntColonyParams(prev => ({
                                    ...prev,
                                    p: Number(value)
                                }))}
                                placeholder="Випаровування"
                                min={0}
                                max={1}
                                step={0.1}
                            />
                        </div>
                        <div className="flex gap-2 items-center max-w-30">
                        <label className="text-gray-500 text-[14px]">τ0:</label>
                            <ValidatedInput
                                type="number"
                                value={antColonyParams.tau}
                                onChange={(value) => setAntColonyParams(prev => ({
                                    ...prev,
                                    tau: Number(value)
                                }))}
                                placeholder="Початковий феромон"
                                min={0}
                                step={0.1}
                            />
                        </div>
                    </div>
                </CardContent>
            </Card>

            <Card className="w-full overflow-auto ">
                <div className="mx-6 max-w-2xl flex-col gap-2">
                    <div className="flex my-5">
                        <Button onClick={handleSolve}>Solve</Button>
                    </div>
                    <h2 className="mt-6 mb-4">Ймовірнісний алгоритм</h2>
                    <Matrix
                        matrix={probSolution}
                        setMatrix={() => {}}
                        columnLabels={columnLabels}
                        setColumnLabels={setColumnLabels}
                        rowLabels={rowLabels}
                        setRowLabels={setRowLabels}
                        isDisabled={true}
                        showControls={false}
                    />
                    <div className="flex gap-2 mt-6 my-5 items-center max-w-30">
                        <ValidatedInput type="number" disabled id="output" value={probValue} placeholder="Output"/>
                    </div>
                    <h2 className="mt-6 mb-4">Алгоритм мурашиних колоній</h2>
                    <Matrix
                        matrix={antSolution}
                        setMatrix={() => {}}
                        columnLabels={columnLabels}
                        setColumnLabels={setColumnLabels}
                        rowLabels={rowLabels}
                        setRowLabels={setRowLabels}
                        isDisabled={true}
                        showControls={false}
                    />
                    <div className="flex gap-2 mt-6 my-5 items-center max-w-30">
                        <ValidatedInput type="number" disabled id="output" value={antValue} placeholder="Output"/>
                    </div>
                </div>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle>Графік порівняння алгоритмів</CardTitle>
                </CardHeader>
                <CardContent>
                    <Chart data={chartData}/>
                </CardContent>
            </Card>
        </div>
    )
}
