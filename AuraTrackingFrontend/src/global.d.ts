/// <reference types="@solidjs/start/env" />

// SharedArrayBuffer types
interface SharedArrayBuffer {
  readonly byteLength: number;
  slice(begin: number, end?: number): SharedArrayBuffer;
}

declare var SharedArrayBuffer: {
  prototype: SharedArrayBuffer;
  new (byteLength: number): SharedArrayBuffer;
};

// Atomics
declare namespace Atomics {
  function add(typedArray: Int32Array, index: number, value: number): number;
  function and(typedArray: Int32Array, index: number, value: number): number;
  function compareExchange(
    typedArray: Int32Array,
    index: number,
    expectedValue: number,
    replacementValue: number
  ): number;
  function exchange(typedArray: Int32Array, index: number, value: number): number;
  function isLockFree(size: number): boolean;
  function load(typedArray: Int32Array, index: number): number;
  function notify(typedArray: Int32Array, index: number, count?: number): number;
  function or(typedArray: Int32Array, index: number, value: number): number;
  function store(typedArray: Int32Array, index: number, value: number): number;
  function sub(typedArray: Int32Array, index: number, value: number): number;
  function wait(
    typedArray: Int32Array,
    index: number,
    value: number,
    timeout?: number
  ): "ok" | "not-equal" | "timed-out";
  function xor(typedArray: Int32Array, index: number, value: number): number;
}

// Worker types
declare module "*.worker.ts" {
  const WorkerFactory: new () => Worker;
  export default WorkerFactory;
}

