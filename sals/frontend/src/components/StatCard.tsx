import React from 'react';
import { motion } from 'motion/react';
import { LucideIcon } from 'lucide-react';
import { cn } from '../lib/utils';

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: LucideIcon;
  trend?: {
    value: number;
    isPositive: boolean;
  };
  className?: string;
  iconClassName?: string;
}

export const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  subtitle,
  icon: Icon,
  trend,
  className,
  iconClassName,
}) => {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className={cn(
        "p-5 rounded-xl bg-white border border-slate-200 shadow-sm flex flex-col justify-between hover:border-slate-300 transition-colors",
        className
      )}
    >
      <div className="flex justify-between items-start mb-2">
        <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest leading-none">{title}</p>
        <div className={cn("p-1.5 rounded-lg opacity-80", iconClassName)}>
          <Icon className="w-4 h-4" />
        </div>
      </div>
      
      <div className="flex flex-col gap-1">
        <div className="flex items-baseline gap-2">
          <h3 className="text-3xl font-bold tracking-tighter text-slate-900">{value}</h3>
          {title === "SLA Compliance" && <span className="text-sm font-bold text-slate-400 -ml-1">%</span>}
          {trend && (
            <span className={cn(
              "text-[10px] font-mono font-bold",
              trend.isPositive ? "text-emerald-500" : "text-rose-500"
            )}>
              {trend.isPositive ? '↑' : '↓'} {trend.value}%
            </span>
          )}
        </div>
        {subtitle && <p className="text-[11px] text-slate-400 font-medium">{subtitle}</p>}
      </div>

      {title === "SLA Compliance" && (
        <div className="mt-4 w-full bg-slate-100 h-1.5 rounded-full overflow-hidden">
          <div 
            className="bg-emerald-500 h-full transition-all duration-1000" 
            style={{ width: value.toString() }}
          ></div>
        </div>
      )}
    </motion.div>
  );
};
