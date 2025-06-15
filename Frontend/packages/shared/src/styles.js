import { css, unsafeCSS } from 'lit'
import styles from './index.css?inline'

// Convert imported CSS string into a Lit CSSResult
export const sharedStyles = css`${unsafeCSS(styles)}`