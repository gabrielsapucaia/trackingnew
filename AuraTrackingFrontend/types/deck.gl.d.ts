// Type declarations for @deck.gl packages v8.x
// These packages don't include TypeScript types in v8.x

declare module '@deck.gl/core' {
  export interface LayerProps<D = unknown> {
    id: string;
    data?: D[] | null;
    visible?: boolean;
    opacity?: number;
    pickable?: boolean;
    autoHighlight?: boolean;
    highlightColor?: number[];
    updateTriggers?: Record<string, unknown>;
    [key: string]: unknown;
  }

  export class Layer<D = unknown, P extends LayerProps<D> = LayerProps<D>> {
    constructor(props: P);
    id: string;
    props: P;
  }

  export interface ViewState {
    latitude: number;
    longitude: number;
    zoom: number;
    bearing?: number;
    pitch?: number;
  }

  export interface PickingInfo {
    object?: unknown;
    layer?: Layer | null;
    x: number;
    y: number;
    coordinate?: [number, number];
    index?: number;
    [key: string]: unknown;
  }

  export interface DeckProps {
    viewState?: ViewState;
    initialViewState?: ViewState;
    controller?: boolean | object;
    layers?: Layer[];
    onViewStateChange?: (params: { viewState: ViewState }) => void;
    onError?: (error: Error) => void;
    onClick?: (info: PickingInfo, event: MouseEvent) => void;
    getCursor?: (params: { isDragging: boolean; isHovering: boolean }) => string;
    style?: React.CSSProperties;
    [key: string]: unknown;
  }

  export class Deck {
    constructor(props: DeckProps);
  }
}

declare module '@deck.gl/layers' {
  import { Layer, LayerProps } from '@deck.gl/core';

  export interface ScatterplotLayerProps<D = unknown> extends LayerProps<D> {
    getPosition?: (d: D) => [number, number] | [number, number, number];
    getRadius?: number | ((d: D) => number);
    getColor?: number[] | ((d: D) => number[]);
    getFillColor?: number[] | ((d: D) => number[]);
    getLineColor?: number[] | ((d: D) => number[]);
    radiusScale?: number;
    radiusMinPixels?: number;
    radiusMaxPixels?: number;
    radiusUnits?: 'meters' | 'pixels';
    lineWidthMinPixels?: number;
    lineWidthMaxPixels?: number;
    lineWidthScale?: number;
    lineWidthUnits?: 'meters' | 'pixels';
    stroked?: boolean;
    filled?: boolean;
    billboard?: boolean;
    antialiasing?: boolean;
  }

  export class ScatterplotLayer<D = unknown> extends Layer<D, ScatterplotLayerProps<D>> {
    constructor(props: ScatterplotLayerProps<D>);
  }

  export interface IconLayerProps<D = unknown> extends LayerProps<D> {
    getPosition?: (d: D) => [number, number] | [number, number, number];
    getIcon?: (d: D) => string | object;
    getSize?: number | ((d: D) => number);
    getColor?: number[] | ((d: D) => number[]);
    getAngle?: number | ((d: D) => number);
    iconAtlas?: string;
    iconMapping?: object;
    sizeScale?: number;
    sizeUnits?: 'meters' | 'pixels';
    sizeMinPixels?: number;
    sizeMaxPixels?: number;
    billboard?: boolean;
  }

  export class IconLayer<D = unknown> extends Layer<D, IconLayerProps<D>> {
    constructor(props: IconLayerProps<D>);
  }

  export interface PathLayerProps<D = unknown> extends LayerProps<D> {
    getPath?: (d: D) => number[][] | Float32Array | Float64Array;
    getColor?: number[] | ((d: D) => number[]);
    getWidth?: number | ((d: D) => number);
    widthScale?: number;
    widthMinPixels?: number;
    widthMaxPixels?: number;
    widthUnits?: 'meters' | 'pixels';
    capRounded?: boolean;
    jointRounded?: boolean;
    billboard?: boolean;
  }

  export class PathLayer<D = unknown> extends Layer<D, PathLayerProps<D>> {
    constructor(props: PathLayerProps<D>);
  }

  export interface PolygonLayerProps<D = unknown> extends LayerProps<D> {
    getPolygon?: (d: D) => number[][] | number[][][];
    getFillColor?: number[] | ((d: D) => number[]);
    getLineColor?: number[] | ((d: D) => number[]);
    getLineWidth?: number | ((d: D) => number);
    getElevation?: number | ((d: D) => number);
    filled?: boolean;
    stroked?: boolean;
    extruded?: boolean;
    wireframe?: boolean;
    lineWidthMinPixels?: number;
    lineWidthMaxPixels?: number;
    lineWidthScale?: number;
    lineWidthUnits?: 'meters' | 'pixels';
    elevationScale?: number;
  }

  export class PolygonLayer<D = unknown> extends Layer<D, PolygonLayerProps<D>> {
    constructor(props: PolygonLayerProps<D>);
  }

  export interface GeoJsonLayerProps<D = unknown> extends LayerProps<D> {
    getFillColor?: number[] | ((d: D) => number[]);
    getLineColor?: number[] | ((d: D) => number[]);
    getLineWidth?: number | ((d: D) => number);
    getPointRadius?: number | ((d: D) => number);
    getElevation?: number | ((d: D) => number);
    filled?: boolean;
    stroked?: boolean;
    extruded?: boolean;
    wireframe?: boolean;
    pointType?: string;
    lineWidthMinPixels?: number;
    lineWidthMaxPixels?: number;
    lineWidthScale?: number;
    lineWidthUnits?: 'meters' | 'pixels';
    pointRadiusMinPixels?: number;
    pointRadiusMaxPixels?: number;
    pointRadiusScale?: number;
    pointRadiusUnits?: 'meters' | 'pixels';
  }

  export class GeoJsonLayer<D = unknown> extends Layer<D, GeoJsonLayerProps<D>> {
    constructor(props: GeoJsonLayerProps<D>);
  }

  export interface TextLayerProps<D = unknown> extends LayerProps<D> {
    getPosition?: (d: D) => [number, number] | [number, number, number];
    getText?: (d: D) => string;
    getSize?: number | ((d: D) => number);
    getColor?: number[] | ((d: D) => number[]);
    getAngle?: number | ((d: D) => number);
    getTextAnchor?: string | ((d: D) => string);
    getAlignmentBaseline?: string | ((d: D) => string);
    getPixelOffset?: [number, number] | ((d: D) => [number, number]);
    fontFamily?: string;
    fontWeight?: string | number;
    characterSet?: string | string[];
    sizeScale?: number;
    sizeUnits?: 'meters' | 'pixels';
    sizeMinPixels?: number;
    sizeMaxPixels?: number;
    billboard?: boolean;
    background?: boolean;
    getBackgroundColor?: number[] | ((d: D) => number[]);
    getBorderColor?: number[] | ((d: D) => number[]);
    getBorderWidth?: number | ((d: D) => number);
  }

  export class TextLayer<D = unknown> extends Layer<D, TextLayerProps<D>> {
    constructor(props: TextLayerProps<D>);
  }
}

declare module '@deck.gl/react' {
  import { DeckProps, Layer, ViewState, PickingInfo } from '@deck.gl/core';
  import { ComponentType } from 'react';

  export interface DeckGLProps extends DeckProps {
    viewState?: ViewState;
    initialViewState?: ViewState;
    controller?: boolean | object;
    layers?: Layer[];
    onViewStateChange?: (params: { viewState: ViewState }) => void;
    onError?: (error: Error) => void;
    onClick?: (info: PickingInfo, event: MouseEvent) => void;
    getCursor?: (params: { isDragging: boolean; isHovering: boolean }) => string;
    style?: React.CSSProperties;
    children?: React.ReactNode;
  }

  export const DeckGL: ComponentType<DeckGLProps>;
  export default DeckGL;
}

