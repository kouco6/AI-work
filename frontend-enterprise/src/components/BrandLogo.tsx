import { cn } from '@/lib/utils';
import itcLogo from '../assets/itc-logo.png';

export type BrandLogoProps = {
  /** Hide the wordmark and render only the logo mark. Currently a no-op for the itc lockup. */
  markOnly?: boolean;
  /** Size of the square logo mark in pixels. Reserved for a future square itc icon. */
  markSize?: number;
  className?: string;
  /** Extra classes applied to the logo wrapper (e.g. to hide it responsively). */
  wordmarkClassName?: string;
};

/** itc 品牌标识：官方 itc logo（深色字标 + 红点），透明背景。
 *  ``markOnly``（侧栏折叠态，约 48px 宽）用更小尺寸避免溢出。 */
export default function BrandLogo({ markOnly = false, className, wordmarkClassName }: BrandLogoProps) {
  return (
    <span className={cn('flex items-center overflow-hidden p-[4px]', className)}>
      <img
        src={itcLogo}
        alt="itc"
        className={cn(
          'w-auto select-none object-contain',
          markOnly ? 'h-[15px]' : 'h-[22px]',
          wordmarkClassName,
        )}
        draggable={false}
      />
    </span>
  );
}
