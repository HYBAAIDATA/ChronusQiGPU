import Link from 'next/link';
import { ArrowLeft, Cpu } from 'lucide-react';
import { Button } from '@/components/ui/button';

export default function NotFound() {
  return (
    <div className="min-h-[70vh] flex flex-col items-center justify-center text-center p-8">
      <div className="w-12 h-12 rounded-xl bg-neutral-900 border border-neutral-800 flex items-center justify-center mb-4 text-purple-400">
        <Cpu className="w-6 h-6" />
      </div>
      <h1 className="text-2xl font-bold text-white tracking-tight">404 Â· Destination Not Found</h1>
      <p className="text-sm text-neutral-400 max-w-md mt-2 font-mono">
        The requested representation or route is not registered on the Chronus QiGPU substrate.
      </p>
      <div className="mt-6">
        <Link href="/">
          <Button className="bg-white text-neutral-950 hover:bg-neutral-200 text-xs font-mono">
            <ArrowLeft className="w-3.5 h-3.5 mr-2" />
            Return to Overview
          </Button>
        </Link>
      </div>
    </div>
  );
}
