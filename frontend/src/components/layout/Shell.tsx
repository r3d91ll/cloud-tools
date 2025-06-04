import { Fragment, useState } from 'react'
import { Dialog, Transition } from '@headlessui/react'
import {
  Bars3Icon,
  HomeIcon,
  XMarkIcon,
  CloudIcon,
  CommandLineIcon,
  KeyIcon,
} from '@heroicons/react/24/outline'
import { useRouter } from 'next/router'
import Link from 'next/link'
import clsx from 'clsx'

const navigation = [
  { name: 'Dashboard', href: '/', icon: HomeIcon },
  {
    name: 'AWS',
    href: '/aws',
    icon: CloudIcon,
    children: [
      { name: 'Credentials', href: '/aws/credentials', icon: KeyIcon },
      { name: 'Script Runner', href: '/aws/script-runner', icon: CommandLineIcon },
    ],
  },
]

export default function Shell({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const router = useRouter()

  const isActive = (href: string) => router.pathname === href

  return (
    <>
      <div>
        <Transition.Root show={sidebarOpen} as={Fragment}>
          <Dialog as="div" className="relative z-50 lg:hidden" onClose={setSidebarOpen}>
            <Transition.Child
              as={Fragment}
              enter="transition-opacity ease-linear duration-300"
              enterFrom="opacity-0"
              enterTo="opacity-100"
              leave="transition-opacity ease-linear duration-300"
              leaveFrom="opacity-100"
              leaveTo="opacity-0"
            >
              <div className="fixed inset-0 bg-gray-900/80" />
            </Transition.Child>

            <div className="fixed inset-0 flex">
              <Transition.Child
                as={Fragment}
                enter="transition ease-in-out duration-300 transform"
                enterFrom="-translate-x-full"
                enterTo="translate-x-0"
                leave="transition ease-in-out duration-300 transform"
                leaveFrom="translate-x-0"
                leaveTo="-translate-x-full"
              >
                <Dialog.Panel className="relative mr-16 flex w-full max-w-xs flex-1">
                  <div className="flex grow flex-col gap-y-5 overflow-y-auto bg-gray-900 px-6 pb-4 ring-1 ring-white/10">
                    <div className="flex h-16 shrink-0 items-center">
                      <img
                        className="h-8 w-auto"
                        src="/logo.svg"
                        alt="AWS Script Runner"
                      />
                    </div>
                    <nav className="flex flex-1 flex-col">
                      <ul role="list" className="flex flex-1 flex-col gap-y-7">
                        <li>
                          <ul role="list" className="-mx-2 space-y-1">
                            {navigation.map((item) => (
                              <li key={item.name}>
                                {!item.children ? (
                                  <Link
                                    href={item.href}
                                    className={clsx(
                                      isActive(item.href)
                                        ? 'bg-gray-800 text-white'
                                        : 'text-gray-400 hover:text-white hover:bg-gray-800',
                                      'group flex gap-x-3 rounded-md p-2 text-sm leading-6 font-semibold'
                                    )}
                                  >
                                    <item.icon className="h-6 w-6 shrink-0" aria-hidden="true" />
                                    {item.name}
                                  </Link>
                                ) : (
                                  <div>
                                    <div className="text-gray-400 group flex gap-x-3 rounded-md p-2 text-sm leading-6 font-semibold">
                                      <item.icon className="h-6 w-6 shrink-0" aria-hidden="true" />
                                      {item.name}
                                    </div>
                                    <ul role="list" className="mt-1 px-8">
                                      {item.children.map((child) => (
                                        <li key={child.name}>
                                          <Link
                                            href={child.href}
                                            className={clsx(
                                              isActive(child.href)
                                                ? 'bg-gray-800 text-white'
                                                : 'text-gray-400 hover:text-white hover:bg-gray-800',
                                              'group flex gap-x-3 rounded-md p-2 text-sm leading-6 font-semibold'
                                            )}
                                          >
                                            <child.icon className="h-6 w-6 shrink-0" aria-hidden="true" />
                                            {child.name}
                                          </Link>
                                        </li>
                                      ))}
                                    </ul>
                                  </div>
                                )}
                              </li>
                            ))}
                          </ul>
                        </li>
                      </ul>
                    </nav>
                  </div>
                </Dialog.Panel>
              </Transition.Child>
            </div>
          </Dialog>
        </Transition.Root>

        {/* Static sidebar for desktop */}
        <div className="hidden lg:fixed lg:inset-y-0 lg:z-50 lg:flex lg:w-72 lg:flex-col">
          <div className="flex grow flex-col gap-y-5 overflow-y-auto bg-gray-900 px-6 pb-4">
            <div className="flex h-16 shrink-0 items-center">
              <img
                className="h-8 w-auto"
                src="/logo.svg"
                alt="AWS Script Runner"
              />
            </div>
            <nav className="flex flex-1 flex-col">
              <ul role="list" className="flex flex-1 flex-col gap-y-7">
                <li>
                  <ul role="list" className="-mx-2 space-y-1">
                    {navigation.map((item) => (
                      <li key={item.name}>
                        {!item.children ? (
                          <Link
                            href={item.href}
                            className={clsx(
                              isActive(item.href)
                                ? 'bg-gray-800 text-white'
                                : 'text-gray-400 hover:text-white hover:bg-gray-800',
                              'group flex gap-x-3 rounded-md p-2 text-sm leading-6 font-semibold'
                            )}
                          >
                            <item.icon className="h-6 w-6 shrink-0" aria-hidden="true" />
                            {item.name}
                          </Link>
                        ) : (
                          <div>
                            <div className="text-gray-400 group flex gap-x-3 rounded-md p-2 text-sm leading-6 font-semibold">
                              <item.icon className="h-6 w-6 shrink-0" aria-hidden="true" />
                              {item.name}
                            </div>
                            <ul role="list" className="mt-1 px-8">
                              {item.children.map((child) => (
                                <li key={child.name}>
                                  <Link
                                    href={child.href}
                                    className={clsx(
                                      isActive(child.href)
                                        ? 'bg-gray-800 text-white'
                                        : 'text-gray-400 hover:text-white hover:bg-gray-800',
                                      'group flex gap-x-3 rounded-md p-2 text-sm leading-6 font-semibold'
                                    )}
                                  >
                                    <child.icon className="h-6 w-6 shrink-0" aria-hidden="true" />
                                    {child.name}
                                  </Link>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </li>
                    ))}
                  </ul>
                </li>
              </ul>
            </nav>
          </div>
        </div>

        <div className="lg:pl-72">
          <div className="sticky top-0 z-40 flex h-16 shrink-0 items-center gap-x-4 border-b border-gray-200 bg-white px-4 shadow-sm sm:gap-x-6 sm:px-6 lg:px-8">
            <button
              type="button"
              className="-m-2.5 p-2.5 text-gray-700 lg:hidden"
              onClick={() => setSidebarOpen(true)}
            >
              <span className="sr-only">Open sidebar</span>
              <Bars3Icon className="h-6 w-6" aria-hidden="true" />
            </button>

            {/* Separator */}
            <div className="h-6 w-px bg-gray-900/10 lg:hidden" aria-hidden="true" />

            <div className="flex flex-1 gap-x-4 self-stretch lg:gap-x-6">
              <div className="flex flex-1" />
            </div>
          </div>

          <main className="py-10">
            <div className="px-4 sm:px-6 lg:px-8">{children}</div>
          </main>
        </div>
      </div>
    </>
  )
}